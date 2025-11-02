from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from .models import CharacterTransfer, MarketplaceTransaction, ClaimRequest
from core.admin import BaseModelAdmin


@admin.register(CharacterTransfer)
class CharacterTransferAdmin(BaseModelAdmin):
    list_display = ['char_name', 'char_level', 'seller', 'buyer', 'price', 'currency', 'status', 'listed_at', 'sold_at']
    list_filter = ['status', 'currency', 'listed_at', 'sold_at']
    search_fields = ['char_name', 'char_id', 'old_account', 'new_account', 'seller__username', 'buyer__username']
    readonly_fields = ['currency', 'listed_at', 'sold_at', 'created_at', 'updated_at']
    
    fieldsets = (
        (_('Informações do Personagem'), {
            'fields': ('char_id', 'char_name', 'char_level', 'char_class')
        }),
        (_('Contas'), {
            'fields': ('old_account', 'new_account')
        }),
        (_('Usuários'), {
            'fields': ('seller', 'buyer')
        }),
        (_('Financeiro'), {
            'fields': ('price', 'currency')
        }),
        (_('Status'), {
            'fields': ('status', 'notes')
        }),
        (_('Datas'), {
            'fields': ('listed_at', 'sold_at', 'created_at', 'updated_at')
        }),
    )


@admin.register(MarketplaceTransaction)
class MarketplaceTransactionAdmin(BaseModelAdmin):
    list_display = ['id', 'transfer', 'transaction_type', 'amount', 'currency', 'user', 'status', 'created_at', 'completed_at']
    list_filter = ['transaction_type', 'status', 'currency', 'created_at']
    search_fields = ['transfer__char_name', 'user__username', 'external_reference', 'notes']
    readonly_fields = ['currency', 'created_at', 'updated_at', 'completed_at']
    
    fieldsets = (
        (_('Transferência'), {
            'fields': ('transfer',)
        }),
        (_('Transação'), {
            'fields': ('transaction_type', 'amount', 'currency', 'user')
        }),
        (_('Status'), {
            'fields': ('status', 'notes', 'external_reference')
        }),
        (_('Datas'), {
            'fields': ('created_at', 'updated_at', 'completed_at')
        }),
    )


@admin.register(ClaimRequest)
class ClaimRequestAdmin(BaseModelAdmin):
    list_display = ['id', 'transfer', 'char_id', 'requester', 'status', 'created_at', 'reviewed_at', 'reviewed_by']
    list_filter = ['status', 'created_at', 'reviewed_at']
    search_fields = ['transfer__char_name', 'requester__username', 'reason', 'admin_notes']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        (_('Informações da Reivindicação'), {
            'fields': ('transfer', 'char_id', 'requester', 'reason')
        }),
        (_('Revisão'), {
            'fields': ('status', 'admin_notes', 'reviewed_by', 'reviewed_at')
        }),
        (_('Datas'), {
            'fields': ('created_at', 'updated_at')
        }),
    )

