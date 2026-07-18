from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from app import db
from app.models import Alert, ScrapeConfig
from app.scraper import perform_apparatus_scrape, perform_pstrax_alerts_scrape
from app.socketio_events import emit_alert_update
from app.timezone_utils import local_now
import atexit

# Global scheduler
scheduler = BackgroundScheduler()

# Global app reference for background tasks
_app = None


def check_alerts():
    """Background task to check and update banner alert status"""
    global _app
    if not _app:
        return
    try:
        with _app.app_context():
            now = local_now().replace(tzinfo=None)
            alerts = Alert.query.all()

            for alert in alerts:
                was_active = alert.is_active
                start_time = alert.start_time or alert.created_at
                end_time = alert.end_time

                if start_time <= now <= end_time:
                    alert.is_active = True
                else:
                    alert.is_active = False

                if was_active != alert.is_active:
                    db.session.commit()
                    emit_alert_update(alert.id)
                    print(f"Alert {alert.id} status changed: {'active' if alert.is_active else 'inactive'}")
    except Exception as e:
        print(f"Error checking alerts: {e}")


def scheduled_pstrax_alerts_scrape():
    """Background task for PSTrax open alerts sync."""
    global _app
    if not _app:
        return
    try:
        with _app.app_context():
            perform_pstrax_alerts_scrape()
    except Exception as e:
        print(f"Error in scheduled PSTrax alerts scrape: {e}")


def scheduled_apparatus_scrape():
    """Background task for PSTrax apparatus / fleet status sync."""
    global _app
    if not _app:
        return
    try:
        with _app.app_context():
            perform_apparatus_scrape()
    except Exception as e:
        print(f"Error in scheduled apparatus scrape: {e}")


def _alerts_interval_minutes(config):
    if config and config.scrape_interval:
        try:
            minutes = int(config.scrape_interval)
            if minutes >= 1:
                return minutes
        except (TypeError, ValueError):
            pass
    return 15


def _apparatus_interval_minutes(config):
    if config and getattr(config, 'apparatus_scrape_interval_hours', None):
        try:
            hours = int(config.apparatus_scrape_interval_hours)
            if hours >= 1:
                return hours * 60
        except (TypeError, ValueError):
            pass
    return 24 * 60


def start_background_tasks(app):
    """Start all background tasks"""
    global _app
    _app = app

    with app.app_context():
        scheduler.add_job(
            func=check_alerts,
            trigger=IntervalTrigger(minutes=1),
            id='check_alerts',
            name='Check banner alert status',
            replace_existing=True,
        )

        config = ScrapeConfig.query.first()

        scheduler.add_job(
            func=scheduled_pstrax_alerts_scrape,
            trigger=IntervalTrigger(minutes=_alerts_interval_minutes(config)),
            id='scheduled_pstrax_alerts_scrape',
            name='Scheduled PSTrax alerts scrape',
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )

        scheduler.add_job(
            func=scheduled_apparatus_scrape,
            trigger=IntervalTrigger(minutes=_apparatus_interval_minutes(config)),
            id='scheduled_apparatus_scrape',
            name='Scheduled apparatus scrape',
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )

        scheduler.start()
        print("Background tasks started")
        atexit.register(lambda: scheduler.shutdown())


def update_scrape_schedule():
    """Update PSTrax alerts scrape schedule when interval changes"""
    global _app
    if not _app:
        return
    try:
        with _app.app_context():
            config = ScrapeConfig.query.first()
            minutes = _alerts_interval_minutes(config)
            try:
                scheduler.remove_job('scheduled_pstrax_alerts_scrape')
            except Exception:
                pass
            scheduler.add_job(
                func=scheduled_pstrax_alerts_scrape,
                trigger=IntervalTrigger(minutes=minutes),
                id='scheduled_pstrax_alerts_scrape',
                name='Scheduled PSTrax alerts scrape',
                replace_existing=True,
                max_instances=1,
                coalesce=True,
            )
    except Exception as e:
        print(f"Error updating PSTrax alerts scrape schedule: {e}")


def update_apparatus_scrape_schedule():
    """Reschedule apparatus sync when interval changes."""
    global _app
    if not _app:
        return
    try:
        with _app.app_context():
            config = ScrapeConfig.query.first()
            minutes = _apparatus_interval_minutes(config)
            try:
                scheduler.remove_job('scheduled_apparatus_scrape')
            except Exception:
                pass
            scheduler.add_job(
                func=scheduled_apparatus_scrape,
                trigger=IntervalTrigger(minutes=minutes),
                id='scheduled_apparatus_scrape',
                name='Scheduled apparatus scrape',
                replace_existing=True,
                max_instances=1,
                coalesce=True,
            )
    except Exception as e:
        print(f"Error updating apparatus scrape schedule: {e}")
