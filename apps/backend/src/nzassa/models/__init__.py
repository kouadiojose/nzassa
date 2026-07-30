"""Modèles SQLAlchemy — importer ce package enregistre toutes les tables."""

from nzassa.models.ai import AiActionProposal, AiConversation, AiMessage
from nzassa.models.appointments import Appointment, AppointmentService
from nzassa.models.auth import (
    DeviceSession,
    LoginAttempt,
    Permission,
    RefreshToken,
    Role,
    RolePermission,
    User,
    UserBranch,
    UserRole,
)
from nzassa.models.base import Base
from nzassa.models.business import Branch, Business, BusinessSetting, Employee
from nzassa.models.catalog import (
    Product,
    ProductBrand,
    ProductCategory,
    ProductVariant,
    Service,
    Tax,
    Unit,
)
from nzassa.models.commissions import EmployeeCommission, EmployeeCommissionRule
from nzassa.models.customers import (
    Customer,
    CustomerDebt,
    CustomerTag,
    DebtPayment,
    LoyaltyAccount,
    LoyaltyTransaction,
    Reward,
)
from nzassa.models.expenses import Expense, ExpenseCategory
from nzassa.models.inventory import (
    StockInventory,
    StockInventoryItem,
    StockLevel,
    StockMovement,
    StockTransfer,
    StockTransferItem,
)
from nzassa.models.invoicing import CreditNote, Invoice, InvoiceItem
from nzassa.models.notifications import Notification, NotificationPreference
from nzassa.models.promotions import Coupon, Promotion
from nzassa.models.sales import (
    CashMovement,
    CashRegister,
    CashSession,
    Payment,
    PaymentMethod,
    Refund,
    Sale,
    SaleItem,
)
from nzassa.models.subscriptions import (
    Feature,
    PlanFeature,
    Subscription,
    SubscriptionInvoice,
    SubscriptionPlan,
)
from nzassa.models.suppliers import (
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseReceipt,
    Supplier,
    SupplierContact,
    SupplierPayment,
)
from nzassa.models.system import AuditLog, FeatureFlag, FileAttachment, SyncOperation
from nzassa.models.tenant import Tenant

__all__ = [
    "AiActionProposal",
    "AiConversation",
    "AiMessage",
    "Appointment",
    "AppointmentService",
    "AuditLog",
    "Base",
    "Branch",
    "Business",
    "BusinessSetting",
    "CashMovement",
    "CashRegister",
    "CashSession",
    "Coupon",
    "CreditNote",
    "Customer",
    "CustomerDebt",
    "CustomerTag",
    "DebtPayment",
    "DeviceSession",
    "Employee",
    "EmployeeCommission",
    "EmployeeCommissionRule",
    "Expense",
    "ExpenseCategory",
    "Feature",
    "FeatureFlag",
    "FileAttachment",
    "Invoice",
    "InvoiceItem",
    "LoginAttempt",
    "LoyaltyAccount",
    "LoyaltyTransaction",
    "Notification",
    "NotificationPreference",
    "Payment",
    "PaymentMethod",
    "Permission",
    "PlanFeature",
    "Product",
    "ProductBrand",
    "ProductCategory",
    "ProductVariant",
    "Promotion",
    "PurchaseOrder",
    "PurchaseOrderItem",
    "PurchaseReceipt",
    "RefreshToken",
    "Refund",
    "Reward",
    "Role",
    "RolePermission",
    "Sale",
    "SaleItem",
    "Service",
    "StockInventory",
    "StockInventoryItem",
    "StockLevel",
    "StockMovement",
    "StockTransfer",
    "StockTransferItem",
    "Subscription",
    "SubscriptionInvoice",
    "SubscriptionPlan",
    "Supplier",
    "SupplierContact",
    "SupplierPayment",
    "SyncOperation",
    "Tax",
    "Tenant",
    "Unit",
    "User",
    "UserBranch",
    "UserRole",
]
