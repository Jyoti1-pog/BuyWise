from django.urls import path
from agent import views

urlpatterns = [
    path("health/", views.HealthView.as_view(), name="health"),
    path("agent/session/", views.SessionCreateView.as_view(), name="session-create"),
    path("agent/session/<str:session_id>/", views.SessionDetailView.as_view(), name="session-detail"),
    path("agent/ask/", views.AskView.as_view(), name="ask"),
    path("agent/compare/", views.CompareView.as_view(), name="compare"),
    path("agent/confirm_purchase/", views.ConfirmPurchaseView.as_view(), name="confirm-purchase"),
    path("orders/<str:order_id>/", views.OrderDetailView.as_view(), name="order-detail"),
    path("products/<int:card_id>/", views.ProductDetailView.as_view(), name="product-detail"),
]
