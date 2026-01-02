from django.urls import path

from . import views

urlpatterns = [
    path("customers/<int:customer_id>/summary/", views.api_customer_reversals_summary),
    path("customers/<int:customer_id>/credit-memos/", views.api_customer_credit_memos),
    path("customer-credit-memos/", views.api_customer_credit_memo_create),
    path("customer-credit-memos/<int:credit_memo_id>/post/", views.api_customer_credit_memo_post),
    path("customer-credit-memos/<int:credit_memo_id>/void/", views.api_customer_credit_memo_void),
    path("customer-credit-memos/<int:credit_memo_id>/allocate/", views.api_customer_credit_memo_allocate),
    path("customers/<int:customer_id>/deposits/", views.api_customer_deposits),
    path("customer-deposits/", views.api_customer_deposit_create),
    path("customer-deposits/<int:deposit_id>/apply/", views.api_customer_deposit_apply),
    path("customer-deposits/<int:deposit_id>/void/", views.api_customer_deposit_void),
    path("customers/<int:customer_id>/refunds/", views.api_customer_refunds),
    path("customer-refunds/", views.api_customer_refund_create),
    path("customer-refunds/<int:refund_id>/void/", views.api_customer_refund_void),
]
