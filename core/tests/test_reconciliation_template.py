"""
Integration test to verify reconciliation template renders without TemplateSyntaxError
"""
from django.test import TestCase, Client
from django.contrib.auth.models import User
from core.models import Business, BankAccount


class ReconciliationTemplateTest(TestCase):
    """Test that the reconciliation page template loads without errors"""
    
    def setUp(self):
        """Create test user, business, and bank account"""
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.business = Business.objects.create(
            owner_user=self.user,
            name='Test Business',
            currency='USD'
        )
        self.bank_account = BankAccount.objects.create(
            business=self.business,
            name='Test Bank Account',
            account_number_mask='****1234'
        )
        
    def test_reconciliation_entry_redirects_when_not_logged_in(self):
        """Anonymous users should be redirected to login"""
        response = self.client.get('/reconciliation/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response.url)
        
    def test_reconciliation_page_renders_successfully(self):
        """Authenticated user with business should see the reconciliation page"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get('/reconciliation/')
        
        # Should render successfully (200)
        self.assertEqual(response.status_code, 200)
        
        # Check for the React mount point in the HTML
        self.assertContains(response, 'id="reconciliation-root"')
        
        # Check that bank account ID is passed to the frontend
        self.assertContains(response, f'data-bank-account-id="{self.bank_account.id}"')
        
    def test_reconciliation_page_without_bank_account(self):
        """User with business but no bank accounts should still render page"""
        # Create user without bank account
        user2 = User.objects.create_user(
            username='testuser2',
            email='test2@example.com',
            password='testpass123'
        )
        business2 = Business.objects.create(
            owner_user=user2,
            name='Test Business 2',
            currency='USD'
        )
        
        self.client.login(username='testuser2', password='testpass123')
        response = self.client.get('/reconciliation/')
        
        # Should still render (with empty bank_account_id)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="reconciliation-root"')
        
    def test_reconciliation_specific_account(self):
        """Test accessing reconciliation for a specific bank account"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(f'/reconciliation/{self.bank_account.id}/')
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="reconciliation-root"')
        self.assertContains(response, f'data-bank-account-id="{self.bank_account.id}"')
        
    def test_template_uses_correct_tag_libraries(self):
        """Verify template loads with mb_extras, not vite"""
        self.client.login(username='testuser', password='testpass123')
        
        # This should not raise TemplateSyntaxError about 'vite' tag library
        response = self.client.get('/reconciliation/')
        self.assertEqual(response.status_code, 200)
        
        # The response should include static assets loaded via mb_extras
        # (checking that vite_asset tag works)
        self.assertContains(response, 'reconciliation-root')
