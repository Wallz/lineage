from django.contrib import admin
from django.utils.html import format_html
from .models import PedidoPagamento, Pagamento, WebhookLog
from core.admin import BaseModelAdmin
from django.template.response import TemplateResponse


@admin.register(PedidoPagamento)
class PedidoPagamentoAdmin(BaseModelAdmin):
    list_display = ('usuario', 'valor_pago', 'bonus_aplicado', 'total_creditado', 'metodo', 'status', 'data_criacao')
    list_filter = ('status', 'metodo', 'data_criacao')
    search_fields = ('usuario__username', 'metodo')
    readonly_fields = ('usuario', 'valor_pago', 'moedas_geradas', 'metodo', 'data_criacao', 'bonus_aplicado', 'total_creditado')
    
    fieldsets = (
        ('Informações do Pedido', {
            'fields': ('usuario', 'valor_pago', 'metodo', 'status', 'data_criacao')
        }),
        ('Bônus e Totais', {
            'fields': ('bonus_aplicado', 'total_creditado'),
            'description': 'Informações sobre bônus aplicados e total creditado'
        }),
        ('Campos Legados', {
            'fields': ('moedas_geradas',),
            'description': 'Campo mantido para compatibilidade'
        }),
    )

    actions = ['confirmar_pagamentos']

    @admin.action(description='Confirmar pagamentos selecionados')
    def confirmar_pagamentos(self, request, queryset):
        # Tela de confirmação customizada
        if 'apply' not in request.POST:
            context = {
                'queryset': queryset,
                'opts': self.model._meta,
                'app_label': self.model._meta.app_label,
                'action': 'confirmar_pagamentos',
                'title': 'Confirmar pagamentos selecionados',
                'total': queryset.count(),
            }
            return TemplateResponse(request, 'admin/payment/confirmar_pagamentos.html', context)

        total = 0
        for pedido in queryset:
            if pedido.status != 'CONFIRMADO':
                # Confirma o pedido e aplica os créditos/bônus (marca no histórico o admin)
                pedido.confirmar_pagamento(actor=request.user)
                # Também marca o Pagamento associado como 'paid' para evitar reprocessamento via webhook
                from .models import Pagamento
                pagamento = Pagamento.objects.filter(pedido_pagamento=pedido).first()
                if pagamento and pagamento.status != 'paid':
                    from django.utils import timezone
                    pagamento.status = 'paid'
                    pagamento.processado_em = timezone.now()
                    pagamento.save()
                total += 1
        self.message_user(request, f"{total} pagamento(s) confirmado(s) com sucesso.")

    class Media:
        js = ('admin/js/pedido_pagamento_admin.js',)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('usuario')


@admin.register(Pagamento)
class PagamentoAdmin(BaseModelAdmin):
    list_display = ('id', 'usuario', 'valor', 'status', 'transaction_code', 'pedido_link', 'data_criacao')
    list_filter = ('status', 'data_criacao')
    search_fields = ('usuario__username', 'transaction_code')
    ordering = ('-data_criacao',)
    readonly_fields = ('data_criacao', 'transaction_code')

    actions = ['reconciliar_mercadopago', 'exportar_csv']

    fieldsets = (
        (None, {
            'fields': ('usuario', 'valor', 'status', 'transaction_code', 'pedido_pagamento', 'data_criacao')
        }),
    )

    def pedido_link(self, obj):
        if obj.pedido_pagamento:
            return format_html('<a href="/admin/payment/pedidopagamento/{}/change/">Ver Pedido</a>', obj.pedido_pagamento.id)
        return '-'
    pedido_link.short_description = "Pedido"

    @admin.action(description='Reconciliar pagamentos pendentes (Mercado Pago)')
    def reconciliar_mercadopago(self, request, queryset):
        import mercadopago
        from django.utils import timezone
        from apps.lineage.wallet.utils import aplicar_compra_com_bonus
        from decimal import Decimal
        sdk = mercadopago.SDK(request.settings.MERCADO_PAGO_ACCESS_TOKEN) if hasattr(request, 'settings') else mercadopago.SDK(__import__('django.conf').conf.settings.MERCADO_PAGO_ACCESS_TOKEN)

        reconciliados = 0
        for pagamento in queryset.select_related('pedido_pagamento', 'usuario'):
            if pagamento.status != 'pending':
                continue
            pedido = pagamento.pedido_pagamento
            if not pedido or pedido.metodo != 'MercadoPago':
                continue

            try:
                search = sdk.merchant_order().search({'external_reference': str(pagamento.id)})
                if search.get('status') == 200:
                    results = (search.get('response') or {}).get('elements', [])
                    for order in results:
                        pagamentos_mp = order.get('payments', [])
                        aprovado = any(p.get('status') == 'approved' for p in pagamentos_mp)
                        if aprovado:
                            from django.db import transaction
                            with transaction.atomic():
                                wallet, _ = pedido.usuario.wallet_set.get_or_create(usuario=pagamento.usuario)
                                valor_total, valor_bonus, _ = aplicar_compra_com_bonus(
                                    wallet, Decimal(str(pagamento.valor)), 'MercadoPago'
                                )
                                pagamento.status = 'paid'
                                pagamento.processado_em = timezone.now()
                                pagamento.save()
                                pedido.bonus_aplicado = valor_bonus
                                pedido.total_creditado = valor_total
                                pedido.status = 'CONCLUÍDO'
                                pedido.save()
                                reconciliados += 1
                            break
            except Exception:
                # Continua com próximos itens sem interromper a ação
                continue

        self.message_user(request, f"{reconciliados} pagamento(s) reconciliado(s) com sucesso.")

    @admin.action(description='Exportar CSV dos pagamentos selecionados')
    def exportar_csv(self, request, queryset):
        import csv
        from django.http import HttpResponse
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="pagamentos.csv"'
        writer = csv.writer(response)
        writer.writerow(['ID', 'Usuario', 'Valor', 'Status', 'Transaction Code', 'Pedido ID', 'Criado em', 'Processado em'])
        for p in queryset.select_related('usuario', 'pedido_pagamento'):
            writer.writerow([
                p.id,
                getattr(p.usuario, 'username', ''),
                f"{p.valor:.2f}",
                p.status,
                p.transaction_code or '',
                getattr(p.pedido_pagamento, 'id', ''),
                p.data_criacao.isoformat() if p.data_criacao else '',
                p.processado_em.isoformat() if getattr(p, 'processado_em', None) else '',
            ])
        return response


@admin.register(WebhookLog)
class WebhookLogAdmin(BaseModelAdmin):
    list_display = ('id', 'tipo', 'data_id', 'recebido_em')
    search_fields = ('tipo', 'data_id')
    list_filter = ('tipo', 'recebido_em')
    readonly_fields = ('tipo', 'data_id', 'payload', 'recebido_em')
    ordering = ('-recebido_em',)

    def has_add_permission(self, request):
        return False  # impede a criação manual

    def has_change_permission(self, request, obj=None):
        return False  # impede a edição

    def has_delete_permission(self, request, obj=None):
        return False  # impede a exclusão
