"""
Configurações do Marketplace
"""
import os
from django.conf import settings

# Nome da conta mestre que armazena personagens à venda
MARKETPLACE_MASTER_ACCOUNT = os.getenv(
    'MARKETPLACE_MASTER_ACCOUNT',
    'MARKETPLACE_SYSTEM'
)

# Limite máximo de personagens por conta (padrão do Lineage 2)
MAX_CHARACTERS_PER_ACCOUNT = 7

