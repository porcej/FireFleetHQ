from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from app import db, socketio
from app.models import Task, Alert, ScrapeData, ScrapeConfig, User, Apparatus, PstraxAlert
from app.forms import TaskForm, AlertForm, ScrapeConfigForm, PasswordChangeForm
from app.user_forms import UserForm
from app.admin import admin_required
from app.socketio_events import emit_task_update, emit_alert_update
from app.tasks import update_scrape_schedule, update_apparatus_scrape_schedule
from app.scraper import perform_apparatus_scrape as run_apparatus_scrape
from app.scraper import perform_pstrax_alerts_scrape as run_pstrax_alerts_scrape
from app.timezone_utils import local_now, normalize_timezone_name
from datetime import datetime
from sqlalchemy import func

bp = Blueprint('main', __name__)


@bp.route('/health')
def health():
    """Health check endpoint"""
    try:
        User.query.first()
        db_status = 'healthy'
        db_error = None
    except Exception as e:
        db_status = 'unhealthy'
        db_error = str(e)

    try:
        config = ScrapeConfig.query.first()
        stats = {
            'users': User.query.count(),
            'tasks': Task.query.count(),
            'alerts': Alert.query.count(),
            'apparatus': Apparatus.query.count(),
            'scrape_config_configured': config is not None and bool(
                config.pstrax_username and config.pstrax_password_encrypted
            ),
            'last_apparatus_scrape': (
                config.last_apparatus_scrape.isoformat()
                if config and config.last_apparatus_scrape
                else None
            ),
        }
    except Exception as e:
        stats = {'error': str(e)}

    overall_status = 'healthy' if db_status == 'healthy' else 'unhealthy'
    response = {
        'status': overall_status,
        'timestamp': datetime.utcnow().isoformat(),
        'database': {'status': db_status, 'error': db_error},
        'stats': stats,
    }
    return jsonify(response), 200 if overall_status == 'healthy' else 503


@bp.route('/')
def index():
    """Redirect to dashboard"""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return redirect(url_for('auth.login'))


@bp.route('/dashboard')
@login_required
def dashboard():
    """Main dashboard view"""
    recent_tasks = (
        Task.query.filter_by(completed=False)
        .order_by(Task.priority.asc(), Task.created_at.desc())
        .limit(5)
        .all()
    )
    config = ScrapeConfig.query.first()
    active_alert = Alert.query.filter_by(is_active=True).first()
    return render_template(
        'dashboard.html',
        recent_tasks=recent_tasks,
        active_alert=active_alert,
        last_apparatus_scrape=config.last_apparatus_scrape if config else None,
    )


@bp.route('/reserve')
@login_required
def reserve():
    """Reserve apparatus page (in_service=1 and in_reserve=1)."""
    return render_template('reserve.html')


@bp.route('/pstrax-alerts')
@login_required
def pstrax_alerts():
    """PSTrax Vehicle/Station open alerts page."""
    config = ScrapeConfig.query.first()
    return render_template(
        'pstrax_alerts.html',
        last_alerts_scrape=config.last_alerts_scrape if config else None,
        pstrax_base_url=(config.pstrax_base_url if config else None) or 'https://pstrax.com',
    )


@bp.route('/tasks')
@login_required
def tasks():
    """Task list management page"""
    all_tasks = Task.query.order_by(Task.priority.asc(), Task.created_at.desc()).all()
    form = TaskForm()
    return render_template('tasks.html', tasks=all_tasks, form=form)


@bp.route('/tasks/create', methods=['POST'])
@login_required
@admin_required
def create_task():
    """Create a new task"""
    form = TaskForm()
    if form.validate_on_submit():
        task = Task(
            content=form.content.data,
            completed=form.completed.data,
            priority=form.priority.data,
            user_id=current_user.id,
        )
        db.session.add(task)
        db.session.commit()
        emit_task_update(task.id, action='added')
        flash('Task created successfully!', 'success')
        return redirect(url_for('main.tasks'))
    flash('Error creating task.', 'error')
    return redirect(url_for('main.tasks'))


@bp.route('/tasks/<int:task_id>/update', methods=['POST'])
@login_required
@admin_required
def update_task(task_id):
    """Update an existing task - admin only"""
    task = Task.query.get_or_404(task_id)

    if request.is_json or request.headers.get('Content-Type') == 'application/json':
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'errors': {'content': ['No data provided']}}), 400

        content = data.get('content', '').strip()
        if not content:
            return jsonify({'success': False, 'errors': {'content': ['Task content cannot be empty']}}), 400
        if len(content) > 1000:
            return jsonify({'success': False, 'errors': {'content': ['Task content cannot exceed 1000 characters']}}), 400

        task.content = content
        task.completed = data.get('completed', task.completed)
        task.priority = data.get('priority', task.priority)
        task.updated_at = datetime.utcnow()
        db.session.commit()
        emit_task_update(task.id, action='updated')
        return jsonify({'success': True, 'task': task.to_dict()})

    form = TaskForm()
    if form.validate_on_submit():
        task.content = form.content.data
        task.completed = form.completed.data
        task.priority = form.priority.data
        task.updated_at = datetime.utcnow()
        db.session.commit()
        emit_task_update(task.id, action='updated')
        flash('Task updated successfully!', 'success')
        return redirect(url_for('main.tasks'))

    flash('Error updating task. Please check the form.', 'error')
    return redirect(url_for('main.tasks'))


@bp.route('/tasks/<int:task_id>/toggle', methods=['POST'])
@login_required
def toggle_task(task_id):
    """Toggle task completion status"""
    task = Task.query.get_or_404(task_id)
    task.completed = not task.completed
    task.updated_at = datetime.utcnow()
    db.session.commit()
    action = 'completed' if task.completed else 'uncompleted'
    emit_task_update(task.id, action=action)
    return jsonify({'success': True, 'completed': task.completed})


@bp.route('/tasks/<int:task_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_task(task_id):
    """Delete a task - admin only"""
    task = Task.query.get_or_404(task_id)
    deleted_task_id = task.id
    db.session.delete(task)
    db.session.commit()
    socketio.emit('task_updated', {'id': deleted_task_id, 'action': 'deleted'}, namespace='/')

    if request.headers.get('Content-Type') == 'application/json':
        return jsonify({'success': True, 'id': deleted_task_id})

    flash('Task deleted successfully!', 'success')
    return redirect(url_for('main.tasks'))


@bp.route('/alerts')
@login_required
def alerts():
    """Alert management page"""
    alerts_list = Alert.query.order_by(Alert.created_at.desc()).all()
    form = AlertForm()
    config = ScrapeConfig.query.first()
    default_color = config.get_default_alert_color() if config else 'danger'
    form.color_theme.data = default_color
    return render_template('alerts.html', alerts=alerts_list, form=form)


@bp.route('/alerts/create', methods=['POST'])
@login_required
@admin_required
def create_alert():
    """Create a new alert"""
    form = AlertForm()
    config = ScrapeConfig.query.first()
    default_color = config.get_default_alert_color() if config else 'danger'
    if form.validate_on_submit():
        alert = Alert(
            message=form.message.data,
            start_time=form.start_time.data,
            end_time=form.end_time.data,
            is_active=False,
            created_by=current_user.id,
            color_theme=(form.color_theme.data or default_color).lower(),
        )
        now = local_now().replace(tzinfo=None)
        if not alert.start_time:
            alert.start_time = now
            alert.is_active = now <= alert.end_time
        else:
            alert.is_active = alert.start_time <= now <= alert.end_time

        db.session.add(alert)
        db.session.commit()
        emit_alert_update(alert.id)
        flash('Alert created successfully!', 'success')
        return redirect(url_for('main.alerts'))
    flash('Error creating alert.', 'error')
    return redirect(url_for('main.alerts'))


@bp.route('/alerts/<int:alert_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_alert(alert_id):
    """Edit an existing alert"""
    alert = Alert.query.get_or_404(alert_id)
    form = AlertForm(obj=alert)
    config = ScrapeConfig.query.first()
    default_color = config.get_default_alert_color() if config else 'danger'
    if request.method == 'GET' and not form.color_theme.data:
        form.color_theme.data = alert.color_theme or default_color

    if form.validate_on_submit():
        alert.message = form.message.data
        alert.start_time = form.start_time.data
        alert.end_time = form.end_time.data
        alert.color_theme = (form.color_theme.data or default_color).lower()
        now = local_now().replace(tzinfo=None)
        if not alert.start_time:
            alert.start_time = now
            alert.is_active = now <= alert.end_time
        else:
            alert.is_active = alert.start_time <= now <= alert.end_time
        db.session.commit()
        emit_alert_update(alert.id)
        flash('Alert updated successfully!', 'success')
        return redirect(url_for('main.alerts'))

    return render_template('edit_alert.html', alert=alert, form=form)


@bp.route('/alerts/<int:alert_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_alert(alert_id):
    """Delete an alert"""
    alert = Alert.query.get_or_404(alert_id)
    db.session.delete(alert)
    db.session.commit()
    emit_alert_update()
    flash('Alert deleted successfully!', 'success')
    return redirect(url_for('main.alerts'))


@bp.route('/settings')
@login_required
def settings():
    """Settings page for PSTrax credentials"""
    config = ScrapeConfig.query.first()
    if not config:
        config = ScrapeConfig()
        db.session.add(config)
        db.session.commit()

    if not config.pstrax_base_url:
        config.pstrax_base_url = 'https://pstrax.com'

    form = ScrapeConfigForm()
    form.pstrax_base_url.data = config.pstrax_base_url
    form.pstrax_username.data = config.pstrax_username
    form.scrape_interval.data = str(config.scrape_interval or 15)
    form.apparatus_scrape_interval_hours.data = str(
        getattr(config, 'apparatus_scrape_interval_hours', None) or 24
    )
    form.default_alert_color.data = config.get_default_alert_color()
    form.alerts_font_size.data = config.get_alert_font_size()
    form.app_timezone.data = config.get_app_timezone()
    form.apparatus_statuses.data = config.apparatus_statuses or ''
    form.apparatus_stations.data = config.apparatus_stations or ''

    selected_statuses = set(s.lower() for s in config.get_apparatus_statuses())
    status_rows = (
        db.session.query(func.trim(Apparatus.status))
        .filter(Apparatus.status.isnot(None))
        .filter(func.trim(Apparatus.status) != '')
        .group_by(func.trim(Apparatus.status))
        .order_by(func.trim(Apparatus.status).asc())
        .all()
    )
    apparatus_status_options = []
    seen = set()
    for (status,) in status_rows:
        label = (status or '').strip()
        if not label:
            continue
        key = label.lower()
        seen.add(key)
        apparatus_status_options.append({
            'name': label,
            'selected': key in selected_statuses if selected_statuses else True,
        })
    for status in config.get_apparatus_statuses():
        if status.lower() not in seen:
            apparatus_status_options.append({'name': status, 'selected': True})

    selected_stations = set(s.lower() for s in config.get_apparatus_stations())
    station_rows = (
        db.session.query(func.trim(Apparatus.station))
        .filter(Apparatus.station.isnot(None))
        .filter(func.trim(Apparatus.station) != '')
        .group_by(func.trim(Apparatus.station))
        .order_by(func.trim(Apparatus.station).asc())
        .all()
    )
    apparatus_station_options = []
    seen_stations = set()
    for (station,) in station_rows:
        label = (station or '').strip()
        if not label:
            continue
        key = label.lower()
        seen_stations.add(key)
        apparatus_station_options.append({
            'name': label,
            'selected': key in selected_stations if selected_stations else True,
        })
    for station in config.get_apparatus_stations():
        if station.lower() not in seen_stations:
            apparatus_station_options.append({'name': station, 'selected': True})

    return render_template(
        'settings.html',
        form=form,
        config=config,
        apparatus_status_options=apparatus_status_options,
        apparatus_station_options=apparatus_station_options,
    )


@bp.route('/settings/update', methods=['POST'])
@login_required
@admin_required
def update_settings():
    """Update PSTrax credentials and sync settings"""
    config = ScrapeConfig.query.first()
    if not config:
        config = ScrapeConfig()
        db.session.add(config)

    if not config.pstrax_base_url:
        config.pstrax_base_url = 'https://pstrax.com'

    form = ScrapeConfigForm()
    if form.validate_on_submit():
        if form.pstrax_base_url.data:
            base_url = form.pstrax_base_url.data.strip()
            if base_url and not base_url.startswith(('http://', 'https://')):
                base_url = 'https://' + base_url
            config.pstrax_base_url = base_url or 'https://pstrax.com'
        config.pstrax_username = form.pstrax_username.data
        if form.pstrax_password.data:
            config.set_password(form.pstrax_password.data)
        if form.scrape_interval.data:
            try:
                config.scrape_interval = int(form.scrape_interval.data)
            except ValueError:
                flash('Invalid scrape interval.', 'error')
                return redirect(url_for('main.settings'))
        if form.apparatus_scrape_interval_hours.data:
            try:
                h = int(form.apparatus_scrape_interval_hours.data)
                if h < 1:
                    raise ValueError('min 1')
                config.apparatus_scrape_interval_hours = h
            except ValueError:
                flash('Invalid apparatus sync interval (use whole hours, minimum 1).', 'error')
                return redirect(url_for('main.settings'))
        config.default_alert_color = (form.default_alert_color.data or 'danger').lower()
        if form.alerts_font_size.data:
            config.alerts_font_size = int(form.alerts_font_size.data)
        else:
            config.alerts_font_size = 16
        config.app_timezone = normalize_timezone_name(
            form.app_timezone.data or 'America/New_York'
        )

        # Prefer checkbox lists from the settings UI when present.
        # If every known option is checked, store blank (= no filter / include all).
        status_values = request.form.getlist('apparatus_status_selected')
        station_values = request.form.getlist('apparatus_station_selected')
        known_statuses = request.form.getlist('apparatus_status_known')
        known_stations = request.form.getlist('apparatus_station_known')
        if known_statuses or status_values or 'apparatus_status_selected' in request.form:
            if known_statuses and set(s.lower() for s in status_values) >= set(
                s.lower() for s in known_statuses
            ):
                config.set_apparatus_statuses([])
            else:
                config.set_apparatus_statuses(status_values)
        else:
            config.set_apparatus_statuses(form.apparatus_statuses.data)
        if known_stations or station_values or 'apparatus_station_selected' in request.form:
            if known_stations and set(s.lower() for s in station_values) >= set(
                s.lower() for s in known_stations
            ):
                config.set_apparatus_stations([])
            else:
                config.set_apparatus_stations(station_values)
        else:
            config.set_apparatus_stations(form.apparatus_stations.data)

        db.session.commit()
        update_scrape_schedule()
        update_apparatus_scrape_schedule()
        flash('Settings updated successfully!', 'success')
        return redirect(url_for('main.settings'))

    flash('Error updating settings.', 'error')
    return redirect(url_for('main.settings'))


@bp.app_context_processor
def inject_alert_settings():
    config = ScrapeConfig.query.first()
    default_color = 'danger'
    font_size = 16
    timezone_name = 'America/New_York'
    if config:
        default_color = config.get_default_alert_color()
        font_size = config.get_alert_font_size()
        timezone_name = config.get_app_timezone()
    return {
        'default_alert_color': default_color,
        'alerts_font_size_px': font_size,
        'app_timezone': timezone_name,
    }


@bp.route('/change-password')
@login_required
def change_password():
    """Page for users to change their password"""
    form = PasswordChangeForm()
    return render_template('change_password.html', form=form)


@bp.route('/change-password', methods=['POST'])
@login_required
def update_password():
    """Handle password change"""
    form = PasswordChangeForm()

    if not form.validate_on_submit():
        for field, errors in form.errors.items():
            for error in errors:
                flash(error, 'error')
        return redirect(url_for('main.change_password'))

    if not current_user.check_password(form.current_password.data):
        flash('Current password is incorrect.', 'error')
        return redirect(url_for('main.change_password'))

    if form.new_password.data != form.confirm_password.data:
        flash('New passwords do not match.', 'error')
        return redirect(url_for('main.change_password'))

    current_user.set_password(form.new_password.data)
    db.session.commit()
    flash('Password changed successfully!', 'success')
    return redirect(url_for('main.dashboard'))


@bp.route('/api/alerts/active')
@login_required
def get_active_alert():
    """API endpoint to get active alert"""
    active_alert = Alert.query.filter_by(is_active=True).first()
    if active_alert:
        return jsonify({'alert': active_alert.to_dict()})
    return jsonify({'alert': None})


@bp.route('/api/tasks')
@login_required
def api_tasks():
    """API endpoint to get user tasks"""
    tasks_list = Task.query.filter_by(user_id=current_user.id).order_by(
        Task.priority.asc(), Task.created_at.desc()
    ).all()
    return jsonify({'tasks': [task.to_dict() for task in tasks_list]})


@bp.route('/api/scrape-data')
@login_required
def api_scrape_data():
    """API endpoint to get latest scraped snapshot metadata"""
    latest_scrape = ScrapeData.query.order_by(ScrapeData.scraped_at.desc()).first()
    if latest_scrape:
        return jsonify({
            'data': latest_scrape.get_data(),
            'scraped_at': latest_scrape.scraped_at.isoformat(),
        })
    return jsonify({'data': {}, 'scraped_at': None})


@bp.route('/api/apparatus-list')
@login_required
def api_apparatus_list():
    """Apparatus list from DB (refreshed by department status scraper)."""
    try:
        config = ScrapeConfig.query.first()
        statuses = config.get_apparatus_statuses() if config else []
        stations = config.get_apparatus_stations() if config else []

        query = Apparatus.query
        if statuses:
            status_keys = [s.lower() for s in statuses if str(s).strip()]
            query = query.filter(func.lower(func.trim(Apparatus.status)).in_(status_keys))
        if stations:
            station_keys = [s.lower() for s in stations if str(s).strip()]
            query = query.filter(func.lower(func.trim(Apparatus.station)).in_(station_keys))

        rows = query.order_by(
            Apparatus.checks_due.desc(),
            Apparatus.open_alerts.desc(),
            Apparatus.unit_name.asc(),
        ).all()
        data = [r.to_api_row() for r in rows]
        return jsonify({
            'data': data,
            'status': 'success',
            'count': len(data),
            'statuses': statuses,
            'stations': stations,
            'last_scrape': (
                config.last_apparatus_scrape.isoformat()
                if config and config.last_apparatus_scrape
                else None
            ),
        })
    except Exception as e:
        return jsonify({'error': str(e), 'data': []}), 500


@bp.route('/api/reserve-list')
@login_required
def api_reserve_list():
    """In-service reserve apparatus (in_service=1 and in_reserve=1), grouped by type."""
    try:
        rows = (
            Apparatus.query
            .filter(Apparatus.in_service == 1)
            .filter(Apparatus.in_reserve == 1)
            .order_by(
                Apparatus.vehicle_type.asc(),
                Apparatus.unit_name.asc(),
                Apparatus.app_unit.asc(),
            )
            .all()
        )

        type_counts = {}
        groups = {}
        for row in rows:
            type_label = (row.vehicle_type or '').strip() or 'Unspecified'
            type_counts[type_label] = type_counts.get(type_label, 0) + 1
            groups.setdefault(type_label, []).append({
                'vehicle_id': row.vehicle_id,
                'assignment': row.unit_name or '',
                'app_unit': row.app_unit or '',
                'door_number': row.app_unit or '',
                'station': row.station or '',
                'location': row.station or '',
                'vehicle_type': type_label,
            })

        # Stable type order: alphabetical, Unspecified last
        type_order = sorted(
            type_counts.keys(),
            key=lambda t: (t == 'Unspecified', t.lower()),
        )
        by_type = [
            {
                'vehicle_type': t,
                'count': type_counts[t],
                'apparatus': groups[t],
            }
            for t in type_order
        ]

        return jsonify({
            'status': 'success',
            'total': len(rows),
            'type_counts': [
                {'vehicle_type': t, 'count': type_counts[t]} for t in type_order
            ],
            'by_type': by_type,
        })
    except Exception as e:
        return jsonify({'error': str(e), 'status': 'error'}), 500


@bp.route('/api/pstrax-alerts')
@login_required
def api_pstrax_alerts():
    """PSTrax open alerts from DB (refreshed by alert-list-station scraper)."""
    try:
        config = ScrapeConfig.query.first()
        rows = (
            PstraxAlert.query
            .order_by(
                PstraxAlert.alert_date.desc(),
                PstraxAlert.alert_id.desc(),
            )
            .all()
        )
        data = [r.to_api_row() for r in rows]
        return jsonify({
            'status': 'success',
            'count': len(data),
            'data': data,
            'last_scrape': (
                config.last_alerts_scrape.isoformat()
                if config and config.last_alerts_scrape
                else None
            ),
        })
    except Exception as e:
        return jsonify({'error': str(e), 'data': [], 'status': 'error'}), 500


@bp.route('/api/scrape/apparatus-trigger', methods=['POST'])
@login_required
@admin_required
def trigger_apparatus_scrape():
    """Manually run PSTrax apparatus sync (replaces apparatus table)."""
    try:
        result = run_apparatus_scrape()
        if result and result.get('success'):
            return jsonify({
                'success': True,
                'message': 'Apparatus sync completed',
                'count': result.get('count'),
                'source_url': result.get('source_url'),
            })
        return jsonify({
            'success': False,
            'error': (result or {}).get('error', 'Apparatus sync failed'),
            'details': result,
        }), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/api/scrape/alerts-trigger', methods=['POST'])
@login_required
@admin_required
def trigger_pstrax_alerts_scrape():
    """Manually run PSTrax station alerts sync."""
    try:
        result = run_pstrax_alerts_scrape()
        if result and result.get('success'):
            return jsonify({
                'success': True,
                'message': 'PSTrax alerts sync completed',
                'count': result.get('count'),
                'source_url': result.get('source_url'),
            })
        return jsonify({
            'success': False,
            'error': (result or {}).get('error', 'Alerts sync failed'),
            'details': result,
        }), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/api/scrape/trigger', methods=['POST'])
@login_required
@admin_required
def trigger_scrape():
    """Alias for PSTrax alerts scrape trigger."""
    return trigger_pstrax_alerts_scrape()


@bp.route('/api/scrape/capture-department-status', methods=['POST'])
@login_required
@admin_required
def capture_department_status():
    """Login to PSTrax, fetch department status report, save sample under PSTrax Example/."""
    from pathlib import Path

    sample_dir = Path(__file__).resolve().parent.parent / 'PSTrax Example'
    sample_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    sample_path = sample_dir / f'department-status-report_{stamp}.txt'

    try:
        result = run_apparatus_scrape(save_raw_sample_path=str(sample_path))
        if not result or not result.get('success'):
            # Still useful if we saved a raw body even when parse failed
            if sample_path.exists():
                return jsonify({
                    'success': True,
                    'path': str(sample_path),
                    'count': (result or {}).get('count', 0),
                    'source_url': (result or {}).get('source_url'),
                    'parse_ok': False,
                    'error': (result or {}).get('error'),
                })
            return jsonify({
                'success': False,
                'error': (result or {}).get('error', 'Capture failed'),
                'details': result,
            }), 500
        return jsonify({
            'success': True,
            'path': str(sample_path),
            'count': result.get('count'),
            'source_url': result.get('source_url'),
            'kind': result.get('kind'),
            'parse_ok': True,
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/admin/users')
@login_required
@admin_required
def admin_users():
    """Admin page to manage users"""
    users = User.query.order_by(User.created_at.desc()).all()
    form = UserForm()
    return render_template('admin/users.html', users=users, form=form)


@bp.route('/admin/users/create', methods=['POST'])
@login_required
@admin_required
def admin_create_user():
    """Create a new user (admin only)"""
    form = UserForm()
    if form.validate_on_submit():
        existing_user = User.query.filter_by(username=form.username.data).first()
        if existing_user:
            flash(f'Username "{form.username.data}" already exists.', 'error')
            return redirect(url_for('main.admin_users'))

        if not form.password.data:
            flash('Password is required.', 'error')
            return redirect(url_for('main.admin_users'))

        new_user = User(username=form.username.data, is_admin=form.is_admin.data)
        new_user.set_password(form.password.data)
        db.session.add(new_user)
        db.session.commit()
        flash(f'User "{new_user.username}" created successfully!', 'success')
    else:
        flash('Error creating user. Please check the form.', 'error')

    return redirect(url_for('main.admin_users'))


@bp.route('/admin/users/<int:user_id>/delete', methods=['POST'])
@login_required
@admin_required
def admin_delete_user(user_id):
    """Delete a user (admin only)"""
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('You cannot delete your own account.', 'error')
        return redirect(url_for('main.admin_users'))

    username = user.username
    db.session.delete(user)
    db.session.commit()
    flash(f'User "{username}" deleted successfully!', 'success')
    return redirect(url_for('main.admin_users'))


@bp.route('/admin/users/<int:user_id>/toggle-admin', methods=['POST'])
@login_required
@admin_required
def admin_toggle_admin(user_id):
    """Toggle admin status (admin only)"""
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        return jsonify({'error': 'You cannot remove your own admin status'}), 400

    user.is_admin = not user.is_admin
    db.session.commit()
    status = 'granted' if user.is_admin else 'revoked'
    flash(f'Admin status {status} for user "{user.username}".', 'success')
    return jsonify({'success': True, 'is_admin': user.is_admin})
