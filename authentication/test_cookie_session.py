from django.conf import settings
from rest_framework import status

from authentication.models import User
from helpers.testing import TEST_PASSWORD, TenantAPITestCase, make_user

COOKIE = settings.AUTH_REFRESH_COOKIE
COOKIE_MODE = {'HTTP_X_HMS_AUTH_MODE': 'cookie'}


class CookieSessionTests(TenantAPITestCase):
    def setUp(self):
        self.user = make_user(User.UserType.RECEPTIONIST)

    def login(self):
        return self.client.post(
            '/api/v1/auth/login/', {'email': self.user.email, 'password': TEST_PASSWORD}, **COOKIE_MODE
        )

    def refresh(self, **extra):
        return self.client.post('/api/v1/auth/token/refresh/', {}, **extra)

    def test_login_puts_refresh_token_in_httponly_cookie(self):
        response = self.login()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertNotIn('refresh', response.data)
        cookie = response.cookies[COOKIE]
        self.assertTrue(cookie['httponly'])
        self.assertEqual((cookie['path'], cookie['samesite']), ('/api/v1/auth/', 'Lax'))

    def test_refresh_rotates_the_cookie_and_old_one_stops_working(self):
        old = self.login().cookies[COOKIE].value
        response = self.refresh(**COOKIE_MODE)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotEqual(response.cookies[COOKIE].value, old)

        self.client.cookies[COOKIE] = old
        self.assertEqual(self.refresh(**COOKIE_MODE).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_cookie_is_ignored_without_the_cookie_mode_header(self):
        # A cross-site form can't add the header, so it can't use the cookie (CSRF)
        self.login()
        self.assertEqual(self.refresh().status_code, status.HTTP_400_BAD_REQUEST)

    def test_logout_revokes_and_clears_the_cookie(self):
        token = self.login().cookies[COOKIE].value
        response = self.client.post('/api/v1/auth/logout/', {}, **COOKIE_MODE)
        self.assertEqual(response.status_code, status.HTTP_205_RESET_CONTENT)
        self.assertEqual(response.cookies[COOKIE].value, '')

        self.client.cookies[COOKIE] = token
        self.assertEqual(self.refresh(**COOKIE_MODE).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_body_mode_still_works_for_api_clients(self):
        tokens = self.client.post('/api/v1/auth/login/', {'email': self.user.email, 'password': TEST_PASSWORD}).data
        self.assertIn('refresh', tokens)
        self.assertEqual(
            self.client.post('/api/v1/auth/token/refresh/', {'refresh': tokens['refresh']}).status_code,
            status.HTTP_200_OK,
        )
