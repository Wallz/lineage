"""
Comando para criar a conta mestre do marketplace no banco L2.
Esta conta será usada para armazenar temporariamente personagens que estão à venda.
"""
import os
import secrets
import hashlib
import base64
from django.core.management.base import BaseCommand
from django.utils.translation import gettext as _
from apps.lineage.server.database import LineageDB
from utils.dynamic_import import get_query_class

# Importa a classe de queries do Lineage dinamicamente
LineageMarketplace = get_query_class("LineageMarketplace")


class Command(BaseCommand):
    help = 'Cria a conta mestre do marketplace no banco L2'

    def add_arguments(self, parser):
        parser.add_argument(
            '--account-name',
            type=str,
            default='MARKETPLACE_SYSTEM',
            help='Nome da conta mestre (padrão: MARKETPLACE_SYSTEM)'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Força a recriação da conta se ela já existir'
        )

    def generate_password_hash(self, password):
        """
        Gera hash de senha compatível com L2.
        A maioria dos servers L2 usa Base64(SHA1(password)) ou variações.
        Ajuste conforme necessário para seu servidor.
        """
        # Gera o hash SHA1
        sha1_hash = hashlib.sha1(password.encode('utf-8')).digest()
        # Converte para Base64
        return base64.b64encode(sha1_hash).decode('utf-8')
    
    def check_account_exists(self, db, account_name):
        """
        Verifica se a conta já existe no banco L2.
        """
        check_sql = "SELECT login FROM accounts WHERE login = :account_name"
        result = db.select(check_sql, {"account_name": account_name})
        return result and len(result) > 0

    def handle(self, *args, **options):
        account_name = options['account_name']
        force = options['force']

        self.stdout.write(self.style.WARNING(
            f"\n{'='*60}\n"
            f"  CRIAÇÃO DA CONTA MESTRE DO MARKETPLACE NO L2\n"
            f"{'='*60}\n"
        ))

        # Verifica conexão com banco
        db = LineageDB()
        if not db.is_connected():
            self.stdout.write(self.style.ERROR(
                '❌ Não foi possível conectar ao banco do Lineage.'
            ))
            return

        # Verifica se a conta já existe
        existing = self.check_account_exists(db, account_name)

        if existing and not force:
            self.stdout.write(self.style.ERROR(
                f'❌ A conta "{account_name}" já existe no banco L2.\n'
                f'   Use --force para recriá-la.'
            ))
            return

        # Gera uma senha muito forte (64 caracteres)
        password = secrets.token_urlsafe(48)  # Gera ~64 caracteres seguros
        password_hash = self.generate_password_hash(password)

        self.stdout.write(self.style.WARNING(
            f"\n⚠️  ATENÇÃO: Anote esta senha em local MUITO seguro!\n"
            f"{'='*60}\n"
        ))
        self.stdout.write(self.style.SUCCESS(
            f"Conta L2: {account_name}\n"
            f"Senha:    {password}\n"
        ))
        self.stdout.write(self.style.WARNING(
            f"{'='*60}\n"
            f"⚠️  Esta conta será criada no banco L2 AGORA!\n"
            f"{'='*60}\n"
        ))

        try:
            if existing and force:
                # Atualiza a conta existente
                self.stdout.write(self.style.WARNING(
                    f"\n🔄 Atualizando conta existente no banco L2...\n"
                ))
            else:
                # Cria a conta nova
                self.stdout.write(self.style.WARNING(
                    f"\n🔄 Criando conta no banco L2...\n"
                ))
            
            # Usa o método da classe de query (conhece a estrutura do banco)
            success = LineageMarketplace.create_or_update_marketplace_account(
                account_name,
                password_hash
            )
            
            if not success:
                raise Exception("Falha ao criar/atualizar a conta no banco L2")
            
            if existing and force:
                self.stdout.write(self.style.SUCCESS(
                    f'✅ Conta "{account_name}" ATUALIZADA no banco L2!'
                ))
            else:
                self.stdout.write(self.style.SUCCESS(
                    f'✅ Conta "{account_name}" CRIADA no banco L2!'
                ))
            
            # Verifica se a conta foi criada/atualizada corretamente
            if self.check_account_exists(db, account_name):
                self.stdout.write(self.style.SUCCESS(
                    f'\n✅ Verificação: Conta confirmada no banco L2!'
                ))
            else:
                raise Exception("Conta não encontrada após criação/atualização")

            # Instruções finais
            self.stdout.write(self.style.SUCCESS(
                f"\n{'='*60}\n"
                f"  ✅ CONTA CRIADA COM SUCESSO NO BANCO L2!\n"
                f"{'='*60}\n"
            ))
            
            self.stdout.write(self.style.WARNING(
                f"\n🔒 SEGURANÇA:\n"
                f"{'='*60}\n"
                f"✅ A conta foi criada EFETIVAMENTE no banco L2\n"
                f"✅ Ninguém mais pode criar uma conta com este nome\n"
                f"✅ Todos os personagens à venda estarão protegidos\n"
                f"✅ Senha ultra-forte de 64 caracteres gerada\n"
                f"{'='*60}\n"
            ))
            
            self.stdout.write(self.style.WARNING(
                f"\n📋 PRÓXIMOS PASSOS:\n"
                f"{'='*60}\n"
                f"1. Adicione no seu arquivo .env:\n"
                f"   MARKETPLACE_MASTER_ACCOUNT={account_name}\n\n"
                f"2. Guarde a senha em local MUITO seguro\n"
                f"   (não será mostrada novamente)\n\n"
                f"3. ⚠️  NÃO use esta conta para login no jogo!\n"
                f"   (apenas o sistema deve usar)\n\n"
                f"4. Esta conta NÃO tem limite de personagens\n"
                f"   (pode armazenar quantos chars estiverem à venda)\n\n"
                f"5. Reinicie o servidor Django após configurar o .env\n"
                f"{'='*60}\n"
            ))

        except Exception as e:
            self.stdout.write(self.style.ERROR(
                f'\n❌ Erro ao criar/atualizar conta no banco L2: {str(e)}\n'
                f'\n💡 Verifique:\n'
                f'   • Conexão com banco L2 está funcionando?\n'
                f'   • A tabela "accounts" existe no banco?\n'
                f'   • O usuário do banco tem permissão de INSERT/UPDATE?\n'
            ))
            return

        self.stdout.write(self.style.SUCCESS(
            f"\n{'='*60}\n"
            f"  🎉 CONFIGURAÇÃO CONCLUÍDA!\n"
            f"  A conta está PROTEGIDA no banco L2.\n"
            f"{'='*60}\n"
        ))

