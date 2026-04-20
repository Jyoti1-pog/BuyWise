from django.urls import path
from agent import views

urlpatterns = [
    path("health/", views.HealthView.as_view(), name="health"),

    # Session management
    path("agent/session/", views.SessionCreateView.as_view(), name="session-create"),
    path("agent/session/<str:session_id>/", views.SessionDetailView.as_view(), name="session-detail"),

    # Core agent
    path("agent/ask/", views.AskView.as_view(), name="ask"),
    path("agent/compare/", views.CompareView.as_view(), name="compare"),

    # Order flows
    path("agent/confirm_purchase/", views.ConfirmPurchaseView.as_view(), name="confirm-purchase"),
    path("agent/quick_order/", views.QuickOrderView.as_view(), name="quick-order"),

    # Seller Q&A
    path("agent/ask_seller/", views.AskSellerView.as_view(), name="ask-seller"),
    path("agent/seller_qa/<int:product_id>/", views.SellerQAHistoryView.as_view(), name="seller-qa-history"),

    # Video analysis
    path("agent/analyze_video/", views.AnalyzeVideoView.as_view(), name="analyze-video"),

    # Resource lookups
    path("orders/<str:order_id>/", views.OrderDetailView.as_view(), name="order-detail"),
    path("products/<int:card_id>/", views.ProductDetailView.as_view(), name="product-detail"),
]
