from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, BooleanField, DateTimeField, PasswordField, SelectField, IntegerField
from wtforms.validators import DataRequired, Optional, Length, NumberRange
from wtforms.widgets import TextArea
from app.timezone_utils import TIMEZONE_CHOICES

ALERT_COLOR_CHOICES = [
    ('primary', 'Primary'),
    ('secondary', 'Secondary'),
    ('success', 'Success'),
    ('danger', 'Danger'),
    ('warning', 'Warning'),
    ('info', 'Info'),
    ('dark', 'Dark'),
    ('light', 'Light')
]


class TaskForm(FlaskForm):
    """Form for creating/editing tasks"""
    content = TextAreaField('Task Content', validators=[DataRequired(), Length(min=1, max=1000)])
    completed = BooleanField('Completed', default=False)
    priority = SelectField(
        'Priority',
        choices=[(1, 'High'), (2, 'Medium'), (3, 'Low')],
        coerce=int,
        default=2,
        validators=[DataRequired()],
    )


class AlertForm(FlaskForm):
    """Form for creating/editing alerts"""
    message = TextAreaField(
        'Message',
        validators=[DataRequired(), Length(min=1, max=1000)],
        widget=TextArea(),
        render_kw={"rows": 4},
    )
    start_time = DateTimeField('Start Time', validators=[Optional()], format='%Y-%m-%dT%H:%M')
    end_time = DateTimeField('End Time', validators=[DataRequired()], format='%Y-%m-%dT%H:%M')
    color_theme = SelectField(
        'Color Theme', choices=ALERT_COLOR_CHOICES, default='danger', validators=[DataRequired()]
    )


class ScrapeConfigForm(FlaskForm):
    """Form for PSTrax credentials and apparatus sync configuration"""
    pstrax_base_url = StringField('Base URL', validators=[Optional(), Length(max=255)])
    pstrax_username = StringField('Username', validators=[Optional(), Length(max=255)])
    pstrax_password = PasswordField('Password', validators=[Optional()])
    scrape_interval = StringField('PSTrax alerts scrape interval (minutes)', validators=[Optional()])
    apparatus_scrape_interval_minutes = StringField(
        'Apparatus sync interval (minutes)', validators=[Optional()]
    )
    default_alert_color = SelectField(
        'Default Alert Color', choices=ALERT_COLOR_CHOICES, default='danger', validators=[DataRequired()]
    )
    alerts_font_size = IntegerField(
        'Alerts Font Size (px)', default=16, validators=[Optional(), NumberRange(min=12, max=48)]
    )
    app_timezone = SelectField(
        'Timezone',
        choices=TIMEZONE_CHOICES,
        default='America/New_York',
        validators=[DataRequired()],
    )
    apparatus_statuses = StringField(
        'Apparatus statuses (comma-separated; blank = all)',
        validators=[Optional(), Length(max=255)],
    )
    apparatus_stations = StringField(
        'Apparatus stations (comma-separated; blank = all)',
        validators=[Optional(), Length(max=512)],
    )
    reserve_homes = StringField(
        'Reserve Home stations (comma-separated; blank = none)',
        validators=[Optional(), Length(max=512)],
    )


class PasswordChangeForm(FlaskForm):
    """Form for changing user password"""
    current_password = PasswordField('Current Password', validators=[DataRequired()])
    new_password = PasswordField(
        'New Password',
        validators=[DataRequired(), Length(min=6, message='Password must be at least 6 characters long')],
    )
    confirm_password = PasswordField('Confirm New Password', validators=[DataRequired()])
