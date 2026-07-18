import requests
import json
import re
from urllib.parse import urlparse, urljoin, quote
from bs4 import BeautifulSoup
from datetime import datetime
from app import db
from sqlalchemy import func, text

from app.models import ScrapeConfig, ScrapeData, Apparatus, PstraxAlert


class PstraxScraper:
    """Web scraper for pstrax website with single-step login"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
        self.session.cookies.clear()
    
    def login(self, username, password, base_url='https://pstrax.com'):
        """
        Login to pstrax website using single-step process.
        Login page URL includes username as query parameter.
        
        Args:
            username: Username for login
            password: Password for login
            base_url: Base URL of pstrax website
        
        Returns:
            tuple: (bool: success, dict: result/error_details)
        """
        error_details = {
            'step': None,
            'status_code': None,
            'message': None,
            'url': None
        }
        
        try:
            # Access login page with username in URL
            error_details['step'] = 'accessing_login_page'
            url_escaped_username = quote(username)
            login_url = f'{base_url.rstrip("/")}/login.php?username={url_escaped_username}'
            
            response = self.session.get(login_url, timeout=10)
            
            if response.status_code != 200:
                error_details['message'] = f"Failed to access login page: Status {response.status_code}"
                error_details['status_code'] = response.status_code
                return False, error_details
            
            # Parse login form
            soup = BeautifulSoup(response.text, 'html.parser')
            form = soup.find('form', {'id': 'loginForm'}) or soup.find('form')
            
            if not form:
                error_details['step'] = 'finding_form'
                error_details['message'] = "Login form not found"
                return False, error_details
            
            # Find username field (id='txtuser_name', name='txtuser_name')
            username_field = (soup.find('input', {'id': 'txtuser_name', 'name': 'txtuser_name'}) or
                            soup.find('input', {'id': 'txtuser_name'}) or
                            soup.find('input', {'name': 'txtuser_name'}))
            
            if not username_field:
                error_details['step'] = 'finding_username_field'
                error_details['message'] = "Username field not found"
                return False, error_details
            
            username_value = username_field.get('value', '') or username
            
            # Find password field (id='txtpassword')
            password_field = soup.find('input', {'id': 'txtpassword'}) or soup.find('input', {'type': 'password'})
            
            if not password_field:
                error_details['step'] = 'finding_password_field'
                error_details['message'] = "Password field not found"
                return False, error_details
            
            password_field_name = password_field.get('name') or 'txtpassword'
            
            # Find CSRF token field (name='_token', id='csrf_token')
            csrf_field = (soup.find('input', {'name': '_token', 'id': 'csrf_token'}) or
                         soup.find('input', {'name': '_token'}) or
                         soup.find('input', {'id': 'csrf_token'}))
            
            if not csrf_field:
                error_details['step'] = 'finding_csrf_token'
                error_details['message'] = "CSRF token field not found"
                return False, error_details
            
            csrf_token = csrf_field.get('value', '')
            if not csrf_token:
                error_details['step'] = 'getting_csrf_token'
                error_details['message'] = "CSRF token value is empty"
                return False, error_details
            
            # Prepare login data
            login_data = {
                'txtuser_name': username_value,
                password_field_name: password,
                '_token': csrf_token
            }
            
            # Include all hidden fields (username might be in a hidden field)
            for hidden in form.find_all('input', type='hidden'):
                name = hidden.get('name')
                if name and name not in login_data:
                    login_data[name] = hidden.get('value', '')
            
            # Submit login
            error_details['step'] = 'submitting_login'
            action = form.get('action', '')
            
            if action:
                if action.startswith('http'):
                    login_post_url = action
                elif action.startswith('/'):
                    parsed_base = urlparse(base_url)
                    login_post_url = f"{parsed_base.scheme}://{parsed_base.netloc}{action}"
                else:
                    login_post_url = urljoin(base_url, action)
            else:
                # Default to /login if no action specified
                parsed_base = urlparse(base_url)
                login_post_url = f"{parsed_base.scheme}://{parsed_base.netloc}/login"
            
            error_details['url'] = login_post_url
            response = self.session.post(login_post_url, data=login_data, timeout=10, allow_redirects=True)
            error_details['status_code'] = response.status_code
            
            # Check if login was successful
            soup = BeautifulSoup(response.text, 'html.parser')
            response_lower = response.text.lower()
            response_url_lower = response.url.lower()
            
            # Check multiple indicators of successful login
            is_not_login_page = 'login' not in response_url_lower
            has_logout_link = 'logout' in response_lower or soup.find('a', href=lambda x: x and 'logout' in x.lower() if x else False)
            has_home_link = soup.find(id='homeLinkButton') is not None
            has_dashboard = 'dashboard' in response_lower
            has_username = username.lower() in response_lower
            page_title = (soup.title.string or '').strip().lower() if soup.title and soup.title.string else ''
            has_login_form = (
                soup.find('form', {'id': 'loginForm'}) is not None
                or soup.find('input', {'id': 'txtpassword'}) is not None
                or soup.find('input', {'name': 'txtuser_name'}) is not None
            )
            looks_like_login_page = (
                has_login_form
                or 'pstrax - login' in page_title
                or 'login.php' in response_url_lower
            )
            
            # Do not treat "URL does not contain login" as success by itself.
            # Some PSTrax login pages can still load at non-login-looking URLs.
            has_positive_success_signal = bool(has_logout_link or has_home_link or has_dashboard)
            if has_positive_success_signal and not looks_like_login_page:
                # Try to find alerts link
                alerts_link = self._find_alerts_link(response.text, base_url, response.url)
                result = {'redirect_url': response.url}
                if alerts_link:
                    result['alerts_link'] = alerts_link
                print(f"Login successful - URL: {response.url}, Indicators: not_login_page={is_not_login_page}, logout_link={has_logout_link}, home_link={has_home_link}")
                return True, result
            
            # Check if we're definitely still on login page (more strict check)
            login_form_present = soup.find('form', {'id': 'loginForm'}) is not None or soup.find('form', action=lambda x: x and 'login' in str(x).lower() if x else False)
            if login_form_present and 'login' in response_url_lower:
                error_details['message'] = f"Login failed - still on login page (Status: {response.status_code}, URL: {response.url})"
                error_details['response_preview'] = response.text[:500]
                return False, error_details
            
            # Uncertain case - status 200, page does not look like login.
            # Proceed, but only when we don't detect login markers.
            if response.status_code == 200:
                if looks_like_login_page:
                    error_details['step'] = 'login_verification'
                    error_details['message'] = "Login failed - response still looks like login page"
                    error_details['response_preview'] = response.text[:500]
                    return False, error_details
                print(f"Uncertain login status - proceeding with status 200, URL: {response.url}")
                alerts_link = self._find_alerts_link(response.text, base_url, response.url)
                result = {'redirect_url': response.url}
                if alerts_link:
                    result['alerts_link'] = alerts_link
                return True, result
            
            # Login failed
            error_details['message'] = f"Login failed - Status: {response.status_code}, URL: {response.url}"
            error_details['response_preview'] = response.text[:500]
            return False, error_details
            
        except requests.RequestException as e:
            error_details['message'] = f"Network error: {str(e)}"
            return False, error_details
        except Exception as e:
            error_details['message'] = f"Unexpected error: {str(e)}"
            return False, error_details

    def _find_alerts_link(self, html_content, base_url, current_url):
        """Find a useful post-login navigation link in HTML (fleet status or alerts)."""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            patterns = (
                'department-status-report',
                'fleet-status',
                'scba-open-alerts',
                'scba/alerts',
            )
            for link in soup.find_all('a', href=True):
                href = (link.get('href') or '').lower()
                if not any(p in href for p in patterns):
                    continue
                full_url = link.get('href')
                if full_url.startswith('http'):
                    return full_url
                if full_url.startswith('/'):
                    parsed = urlparse(base_url)
                    return f"{parsed.scheme}://{parsed.netloc}{full_url}"
                return urljoin(current_url, full_url)
            return None
        except Exception as e:
            print(f"Error finding alerts/status link: {e}")
            return None

    def get_department_status_report(self, base_url='https://app1.pstrax.com'):
        """
        Fetch Fleet Status / Department Status Report data.

        Tries JSON data endpoints first, then the HTML page. Returns
        (response, source_label) for the first usable 200 response.
        """
        base = base_url.rstrip('/')
        candidates = [
            ('POST', f'{base}/department-status-report-data.php', {
                'btnSubmit': 'true',
                'limitSearch': '0',
            }),
            ('POST', f'{base}/department-status-report.php', {
                'btnSubmit': 'true',
                'limitSearch': '0',
            }),
            ('GET', f'{base}/department-status-report-data.php', None),
            ('GET', f'{base}/department-status-report.php', None),
        ]
        headers = {
            'Referer': base + '/',
            'Accept': 'application/json, text/javascript, text/html, */*; q=0.01',
            'X-Requested-With': 'XMLHttpRequest',
        }
        last_response = None
        for method, url, form_data in candidates:
            try:
                if method == 'POST':
                    headers_post = dict(headers)
                    headers_post['Content-Type'] = 'application/x-www-form-urlencoded; charset=UTF-8'
                    resp = self.session.post(
                        url, data=form_data or {}, timeout=120,
                        allow_redirects=True, headers=headers_post,
                    )
                else:
                    resp = self.session.get(
                        url, timeout=120, allow_redirects=True, headers=headers,
                    )
                last_response = resp
                if resp.status_code != 200:
                    continue
                if 'login' in (resp.url or '').lower():
                    continue
                body = (resp.text or '').lstrip()
                if body.startswith('{') or body.startswith('['):
                    return resp, url
                # HTML may still be useful for table parsing
                if '<table' in body.lower() or 'department' in body.lower() or 'fleet' in body.lower():
                    return resp, url
            except requests.RequestException as e:
                print(f"Department status fetch error for {url}: {e}")
                continue
        return last_response, candidates[-1][1]

    def discover_data_url_from_html(self, html, base_url):
        """Find a DataTables/ajax data URL referenced by the report page."""
        if not html:
            return None
        patterns = [
            r'["\']([^"\']*department-status-report[^"\']*data[^"\']*\.php[^"\']*)["\']',
            r'["\']([^"\']*department-status[^"\']*\.php[^"\']*)["\']',
            r'ajax\s*:\s*["\']([^"\']+)["\']',
            r'url\s*:\s*["\']([^"\']+\.php[^"\']*)["\']',
        ]
        base = base_url.rstrip('/')
        for pattern in patterns:
            for match in re.finditer(pattern, html, re.I):
                href = match.group(1)
                if href.startswith('http'):
                    return href
                if href.startswith('/'):
                    parsed = urlparse(base)
                    return f"{parsed.scheme}://{parsed.netloc}{href}"
                return urljoin(base + '/', href)
        return None

    def get_station_alerts(self, base_url='https://app1.pstrax.com'):
        """
        Fetch Vehicle/Station open alerts via alert-list-station-data.php.

        Loads the list page first to collect search form defaults, then POSTs
        with txtstation=all (and related fields) to the JSON data endpoint.
        """
        base = base_url.rstrip('/')
        page_url = f'{base}/alert-list-station.php'
        data_url = f'{base}/alert-list-station-data.php'
        headers = {
            'Referer': base + '/',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        }
        page = self.session.get(page_url, timeout=60, allow_redirects=True, headers=headers)
        if page.status_code != 200 or 'login' in (page.url or '').lower():
            return page, page_url

        soup = BeautifulSoup(page.text or '', 'html.parser')
        form_data = {}
        for el in soup.find_all(['input', 'select', 'textarea']):
            name = el.get('name')
            if not name:
                continue
            if el.name == 'select':
                if name == 'txtstation':
                    form_data[name] = 'all'
                elif name == 'txtcategory':
                    form_data[name] = 'all'
                else:
                    selected = el.find('option', selected=True)
                    opts = el.find_all('option')
                    if selected:
                        form_data[name] = selected.get('value', '')
                    elif opts:
                        form_data[name] = opts[0].get('value', '')
                    else:
                        form_data[name] = ''
            elif el.get('type') in ('checkbox', 'radio'):
                if el.has_attr('checked'):
                    form_data[name] = el.get('value', 'on')
            else:
                form_data[name] = el.get('value') or ''

        form_data['btnSubmit'] = 'true'
        form_data.setdefault('txtstation', 'all')
        form_data.setdefault('txtcategory', 'all')
        form_data.setdefault('txtalertid', '0')

        post_headers = {
            'Referer': page_url,
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'X-Requested-With': 'XMLHttpRequest',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        }
        resp = self.session.post(
            data_url, data=form_data, timeout=120, allow_redirects=True, headers=post_headers
        )
        return resp, data_url


def _parse_response_rows(resp):
    """Return (rows, parsed_payload_or_None, content_kind)."""
    from app.pstrax_apparatus_map import (
        parse_department_status_html,
        parse_department_status_payload,
    )

    text = resp.text or ''
    payload = None
    try:
        payload = resp.json()
    except (ValueError, json.JSONDecodeError):
        try:
            payload = json.loads(text)
        except (ValueError, json.JSONDecodeError):
            payload = None

    if payload is not None:
        rows = parse_department_status_payload(payload)
        if rows:
            return rows, payload, 'json'

    rows = parse_department_status_html(text)
    return rows, payload, 'html'


def _prune_scrape_data_keep_latest(db):
    """Keep only the newest scrape_data row."""
    count = ScrapeData.query.count()
    if count <= 1:
        return
    latest_id = db.session.query(func.max(ScrapeData.id)).scalar()
    if latest_id is None:
        return
    deleted = ScrapeData.query.filter(ScrapeData.id != latest_id).delete(
        synchronize_session=False
    )
    db.session.commit()
    if deleted >= 100:
        try:
            with db.engine.connect() as conn:
                conn.execute(text("VACUUM"))
                conn.commit()
        except Exception as e:
            print(f"VACUUM after scrape_data prune skipped: {e}")


def perform_apparatus_scrape(save_raw_sample_path=None):
    """Fetch PSTrax department status report and replace the apparatus table."""
    from app import db
    from app.pstrax_apparatus_map import extract_vehicle_id

    with db.session.no_autoflush:
        config = ScrapeConfig.query.first()
        if not config or not config.pstrax_username or not config.pstrax_password_encrypted:
            print("Apparatus scrape skipped: No credentials configured")
            return {'success': False, 'error': 'No credentials configured'}

        password = config.get_password()
        if not password:
            print("Apparatus scrape skipped: Could not decrypt password")
            return {'success': False, 'error': 'Could not decrypt password'}

        base_url = config.pstrax_base_url or 'https://pstrax.com'
        print(f"Starting apparatus scrape at {base_url}")

        scraper = PstraxScraper()
        login_success, login_result = scraper.login(
            config.pstrax_username, password, base_url=base_url
        )
        if not login_success:
            print(f"Apparatus scrape failed: login unsuccessful — {login_result}")
            return {'success': False, 'error': 'login failed', 'details': login_result}

        resp, source_url = scraper.get_department_status_report(base_url=base_url)
        if resp is None or resp.status_code != 200:
            status = resp.status_code if resp is not None else None
            print(f"Apparatus scrape failed: HTTP {status}")
            return {'success': False, 'error': f'HTTP {status}'}

        # If HTML page, try to discover and fetch a JSON data URL
        rows, payload, kind = _parse_response_rows(resp)
        if kind == 'html' and not rows:
            data_url = scraper.discover_data_url_from_html(resp.text, base_url)
            if data_url:
                print(f"Discovered data URL: {data_url}")
                headers = {
                    'Referer': base_url.rstrip('/') + '/',
                    'Accept': 'application/json, text/javascript, */*; q=0.01',
                    'X-Requested-With': 'XMLHttpRequest',
                    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                }
                try:
                    data_resp = scraper.session.post(
                        data_url, data={'btnSubmit': 'true'}, timeout=120,
                        allow_redirects=True, headers=headers,
                    )
                    if data_resp.status_code == 200:
                        rows, payload, kind = _parse_response_rows(data_resp)
                        resp = data_resp
                        source_url = data_url
                except requests.RequestException as e:
                    print(f"Discovered data URL fetch failed: {e}")

        if save_raw_sample_path:
            try:
                with open(save_raw_sample_path, 'w', encoding='utf-8') as fh:
                    fh.write(resp.text or '')
                print(f"Wrote raw sample to {save_raw_sample_path}")
            except OSError as e:
                print(f"Could not write raw sample: {e}")

        if not rows:
            print("Apparatus scrape failed: no rows parsed from response")
            return {
                'success': False,
                'error': 'no rows parsed',
                'source_url': source_url,
                'content_type': resp.headers.get('Content-Type'),
                'preview': (resp.text or '')[:500],
            }

        now = datetime.utcnow()
        stored = 0
        skipped = 0
        try:
            Apparatus.query.delete(synchronize_session=False)
            for item in rows:
                try:
                    if extract_vehicle_id(item) is None:
                        # Synthesize a stable id from unit+station when needed
                        unit = str(
                            item.get('app_name')
                            or item.get('unit_name')
                            or item.get('unit')
                            or item.get('name')
                            or ''
                        )
                        station = str(item.get('station_name') or item.get('station') or '')
                        synth = abs(hash(f"{unit}|{station}")) % (10**9)
                        item = dict(item)
                        item['vehicleid'] = synth
                    db.session.add(Apparatus.from_pstrax_row(item, now))
                    stored += 1
                except (ValueError, TypeError, KeyError) as ex:
                    skipped += 1
                    print(f"Apparatus scrape: skip row: {ex}")

            # Store latest raw snapshot for debugging / dashboard
            scrape_row = ScrapeData(
                scraped_at=now,
                data=json.dumps({
                    'source_url': source_url,
                    'kind': kind,
                    'count': stored,
                    'payload': payload if isinstance(payload, (dict, list)) else None,
                }, default=str),
            )
            db.session.add(scrape_row)
            config.last_apparatus_scrape = now
            config.last_scrape = now
            db.session.commit()
            _prune_scrape_data_keep_latest(db)
        except Exception as e:
            db.session.rollback()
            print(f"Apparatus scrape failed storing rows: {e}")
            return {'success': False, 'error': str(e)}

        print(f"Apparatus scrape completed: {stored} rows stored ({skipped} skipped) from {source_url}")
        from app.socketio_events import emit_apparatus_updated, emit_scrape_update
        emit_apparatus_updated()
        emit_scrape_update({'action': 'refresh', 'count': stored})
        return {
            'success': True,
            'count': stored,
            'skipped': skipped,
            'source_url': source_url,
            'kind': kind,
        }


def perform_pstrax_alerts_scrape(save_raw_sample_path=None):
    """Fetch PSTrax station open alerts and replace the pstrax_alert table."""
    from app import db
    from app.pstrax_alerts_map import extract_alert_id, parse_alerts_payload

    with db.session.no_autoflush:
        config = ScrapeConfig.query.first()
        if not config or not config.pstrax_username or not config.pstrax_password_encrypted:
            print("Alerts scrape skipped: No credentials configured")
            return {'success': False, 'error': 'No credentials configured'}

        password = config.get_password()
        if not password:
            print("Alerts scrape skipped: Could not decrypt password")
            return {'success': False, 'error': 'Could not decrypt password'}

        base_url = config.pstrax_base_url or 'https://pstrax.com'
        print(f"Starting PSTrax alerts scrape at {base_url}")

        scraper = PstraxScraper()
        login_success, login_result = scraper.login(
            config.pstrax_username, password, base_url=base_url
        )
        if not login_success:
            print(f"Alerts scrape failed: login unsuccessful — {login_result}")
            return {'success': False, 'error': 'login failed', 'details': login_result}

        resp, source_url = scraper.get_station_alerts(base_url=base_url)
        if resp is None or resp.status_code != 200:
            status = resp.status_code if resp is not None else None
            print(f"Alerts scrape failed: HTTP {status}")
            return {'success': False, 'error': f'HTTP {status}'}

        if save_raw_sample_path:
            try:
                with open(save_raw_sample_path, 'w', encoding='utf-8') as fh:
                    fh.write(resp.text or '')
                print(f"Wrote raw alerts sample to {save_raw_sample_path}")
            except OSError as e:
                print(f"Could not write raw alerts sample: {e}")

        payload = None
        try:
            payload = resp.json()
        except (ValueError, json.JSONDecodeError):
            try:
                payload = json.loads(resp.text or '')
            except (ValueError, json.JSONDecodeError):
                payload = None

        rows = parse_alerts_payload(payload)
        if not rows:
            print("Alerts scrape failed: no rows parsed from response")
            return {
                'success': False,
                'error': 'no rows parsed',
                'source_url': source_url,
                'preview': (resp.text or '')[:500],
            }

        now = datetime.utcnow()
        stored = 0
        skipped = 0
        try:
            PstraxAlert.query.delete(synchronize_session=False)
            for item in rows:
                try:
                    if extract_alert_id(item) is None:
                        skipped += 1
                        continue
                    db.session.add(PstraxAlert.from_pstrax_row(item, now))
                    stored += 1
                except (ValueError, TypeError, KeyError) as ex:
                    skipped += 1
                    print(f"Alerts scrape: skip row: {ex}")

            config.last_alerts_scrape = now
            config.last_scrape = now
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"Alerts scrape failed storing rows: {e}")
            return {'success': False, 'error': str(e)}

        print(f"Alerts scrape completed: {stored} rows stored ({skipped} skipped) from {source_url}")
        from app.socketio_events import emit_pstrax_alerts_updated
        emit_pstrax_alerts_updated()
        return {
            'success': True,
            'count': stored,
            'skipped': skipped,
            'source_url': source_url,
        }


# Backward-compatible alias used by older call sites / docs
perform_scrape = perform_pstrax_alerts_scrape
