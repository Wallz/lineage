from django.shortcuts import render
from django.http import HttpResponseNotFound
import logging
from functools import lru_cache
from .models import SystemResource  # import fixo, não dentro da função

logger = logging.getLogger(__name__)


class ResourceAccessMiddleware:
    """
    Middleware para verificar se os recursos estão ativos antes de permitir acesso
    """

    def __init__(self, get_response):
        self.get_response = get_response

        # Mapeamento de caminhos de URL para recursos
        self.path_mapping = {
            # Shop
            '/app/shop/': 'shop_module',
            '/app/shop/cart/': 'shop_cart',
            '/app/shop/cart/add-item/': 'shop_cart',
            '/app/shop/cart/add-package/': 'shop_cart',
            '/app/shop/cart/checkout/': 'shop_checkout',
            '/app/shop/purchases/': 'shop_purchases',
            '/app/shop/manager/dashboard/': 'shop_dashboard',

            # Wallet
            '/app/wallet/': 'wallet_module',
            '/app/wallet/dashboard/': 'wallet_dashboard',
            '/app/wallet/transfer/': 'wallet_transfer',
            '/app/wallet/history/': 'wallet_history',

            # Social
            '/social/': 'social_module',
            '/social/feed/': 'social_feed',
            '/social/profile/': 'social_profile',
            '/social/search/': 'social_search',

            # Games
            '/app/game/': 'games_module',
            '/app/game/battle-pass/': 'battle_pass',
            '/app/game/box-opening/': 'box_opening',
            '/app/game/roulette/': 'roulette',

            # Auction
            '/app/auction/': 'auction_module',
            '/app/auction/list/': 'auction_list',
            '/app/auction/create/': 'auction_create',

            # Inventory
            '/app/inventory/': 'inventory_module',
            '/app/inventory/dashboard/': 'inventory_dashboard',

            # Payment
            '/app/payment/': 'payment_module',
            '/app/payment/process/': 'payment_process',
            '/app/payment/history/': 'payment_history',
        }

        # Hierarquia pré-definida
        self.hierarchy = {
            'battle_pass': 'games_module',
            'box_opening': 'games_module',
            'roulette': 'games_module',
            'shop_dashboard': 'shop_module',
            'shop_items': 'shop_module',
            'shop_packages': 'shop_module',
            'shop_cart': 'shop_module',
            'shop_checkout': 'shop_module',
            'shop_purchases': 'shop_module',
            'wallet_dashboard': 'wallet_module',
            'wallet_transfer': 'wallet_module',
            'wallet_history': 'wallet_module',
            'social_feed': 'social_module',
            'social_profile': 'social_module',
            'social_search': 'social_module',
            'auction_list': 'auction_module',
            'auction_create': 'auction_module',
            'inventory_dashboard': 'inventory_module',
            'payment_process': 'payment_module',
            'payment_history': 'payment_module',
        }

    def __call__(self, request):
        logger.debug(f"Middleware: verificando caminho {request.path}")

        if not self._check_resource_access(request.path):
            logger.warning(f"Recurso inativo detectado para caminho: {request.path}")
            return self._handle_inactive_resource(request)

        return self.get_response(request)

    def _check_resource_access(self, path: str) -> bool:
        """Verifica se o recurso solicitado está ativo"""
        try:
            resource_name = self.path_mapping.get(path)

            # se não achou, tenta por prefixo (mais caro, só se necessário)
            if not resource_name:
                for mapped_path, mapped_resource in self.path_mapping.items():
                    if path.startswith(mapped_path):
                        resource_name = mapped_resource
                        break

            if resource_name:
                return self._check_resource_hierarchy(resource_name)

            return True  # Se não está mapeado, passa direto

        except Exception as e:
            logger.error(f"Erro em _check_resource_access: {e}")
            return True

    @lru_cache(maxsize=256)
    def _check_resource_hierarchy(self, resource_name: str) -> bool:
        """Verifica recurso e seu módulo pai com cache"""
        parent = self.hierarchy.get(resource_name)

        if parent and not SystemResource.is_resource_active(parent):
            logger.debug(f"Módulo pai '{parent}' inativo -> bloqueando '{resource_name}'")
            return False

        return SystemResource.is_resource_active(resource_name)

    def _handle_inactive_resource(self, request):
        """Retorna resposta para recurso inativo"""
        template = 'resources/404.html' if request.user.is_staff else 'errors/404.html'

        try:
            return render(request, template, status=404)
        except Exception as e:
            logger.error(f"Erro ao renderizar {template}: {e}")
            msg = (
                '<h1 style="color: #dc3545;">404 - Recurso Indisponível</h1>'
                '<p>Este recurso está temporariamente indisponível.</p>'
                if request.user.is_staff else
                '<h1 style="color: #dc3545;">404 - Página não encontrada</h1>'
                '<p>A página que você está procurando não existe ou foi movida.</p>'
            )
            return HttpResponseNotFound(
                f'<!DOCTYPE html><html><head><title>Erro</title></head>'
                f'<body style="font-family: Arial; text-align:center; padding:50px;">'
                f'{msg}<p><a href="/pages/dashboard/">Voltar ao Dashboard</a></p>'
                f'</body></html>'
            )
