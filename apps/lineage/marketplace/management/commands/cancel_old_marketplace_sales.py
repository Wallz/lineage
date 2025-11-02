"""
Comando para cancelar vendas antigas do marketplace que foram criadas antes
da implementação do sistema de conta mestre.

Este comando é útil após a migração para o novo sistema, pois as vendas antigas
não têm os personagens movidos para a conta mestre do sistema.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from apps.lineage.marketplace.models import CharacterTransfer
from apps.lineage.marketplace.config import MARKETPLACE_MASTER_ACCOUNT
from apps.lineage.server.database import LineageDB
from utils.dynamic_import import get_query_class

LineageMarketplace = get_query_class("LineageMarketplace")


class Command(BaseCommand):
    help = 'Cancela vendas antigas do marketplace (modelo antigo, sem conta mestre)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Apenas mostra o que seria feito, sem executar'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Cancela as vendas sem pedir confirmação'
        )
        parser.add_argument(
            '--move-to-master',
            action='store_true',
            help='Ao invés de cancelar, move os personagens para a conta mestre (mantém as vendas ativas)'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        force = options['force']
        move_to_master = options['move_to_master']

        self.stdout.write(self.style.WARNING(
            f"\n{'='*70}\n"
            f"  CANCELAMENTO DE VENDAS ANTIGAS DO MARKETPLACE\n"
            f"{'='*70}\n"
        ))

        # Verifica conexão com banco
        db = LineageDB()
        if not db.is_connected():
            self.stdout.write(self.style.ERROR(
                '❌ Não foi possível conectar ao banco do Lineage.'
            ))
            return

        # Busca vendas ativas
        active_sales = CharacterTransfer.objects.filter(
            status__in=['for_sale', 'pending']
        ).select_related('seller')

        if not active_sales.exists():
            self.stdout.write(self.style.SUCCESS(
                '\n✅ Não há vendas ativas no marketplace.\n'
            ))
            return

        self.stdout.write(self.style.WARNING(
            f"\n📊 Encontradas {active_sales.count()} vendas ativas\n"
        ))

        # Analisa cada venda
        old_sales = []  # Vendas que NÃO estão na conta mestre
        new_sales = []  # Vendas que JÁ estão na conta mestre
        missing_chars = []  # Personagens não encontrados no banco

        for sale in active_sales:
            # Verifica se o personagem existe
            char_details = LineageMarketplace.get_character_details(sale.char_id)
            
            if not char_details:
                missing_chars.append(sale)
                continue
            
            # Verifica se está na conta mestre
            is_in_master = LineageMarketplace.verify_character_ownership(
                sale.char_id,
                MARKETPLACE_MASTER_ACCOUNT
            )
            
            if is_in_master:
                new_sales.append(sale)
            else:
                old_sales.append((sale, char_details.get('account_name', '?')))

        # Relatório
        self.stdout.write(self.style.SUCCESS(f"\n📈 ANÁLISE:"))
        self.stdout.write(f"   • Vendas no NOVO modelo (já na conta mestre): {len(new_sales)}")
        self.stdout.write(self.style.WARNING(
            f"   • Vendas no MODELO ANTIGO (não na conta mestre): {len(old_sales)}"
        ))
        if missing_chars:
            self.stdout.write(self.style.ERROR(
                f"   • Personagens NÃO ENCONTRADOS no banco L2: {len(missing_chars)}"
            ))

        if not old_sales and not missing_chars:
            self.stdout.write(self.style.SUCCESS(
                '\n✅ Todas as vendas já estão no novo modelo! Nada a fazer.\n'
            ))
            return

        # Mostra detalhes das vendas antigas
        if old_sales:
            self.stdout.write(self.style.WARNING(
                f"\n{'='*70}\n"
                f"  VENDAS NO MODELO ANTIGO:\n"
                f"{'='*70}"
            ))
            for sale, current_account in old_sales:
                self.stdout.write(
                    f"\n  ID: {sale.id} | {sale.char_name} (Level {sale.char_level})\n"
                    f"  • Vendedor: {sale.seller.username}\n"
                    f"  • Preço: R$ {sale.price}\n"
                    f"  • Conta atual no L2: {current_account}\n"
                    f"  • Listado em: {sale.listed_at.strftime('%d/%m/%Y %H:%M')}"
                )

        # Mostra personagens não encontrados
        if missing_chars:
            self.stdout.write(self.style.ERROR(
                f"\n{'='*70}\n"
                f"  PERSONAGENS NÃO ENCONTRADOS:\n"
                f"{'='*70}"
            ))
            for sale in missing_chars:
                self.stdout.write(
                    f"\n  ID: {sale.id} | {sale.char_name} (char_id: {sale.char_id})\n"
                    f"  • Vendedor: {sale.seller.username}\n"
                    f"  • Listado em: {sale.listed_at.strftime('%d/%m/%Y %H:%M')}\n"
                    f"  • ⚠️ Este personagem não existe mais no banco L2!"
                )

        if dry_run:
            self.stdout.write(self.style.WARNING(
                f"\n{'='*70}\n"
                f"  🔍 MODO DRY-RUN ATIVO\n"
                f"  Nenhuma alteração foi feita.\n"
                f"  Execute novamente sem --dry-run para aplicar as mudanças.\n"
                f"{'='*70}\n"
            ))
            return

        # Confirmação
        if not force:
            self.stdout.write(self.style.WARNING(
                f"\n{'='*70}\n"
                f"  ⚠️  CONFIRMAÇÃO NECESSÁRIA\n"
                f"{'='*70}"
            ))
            
            if move_to_master:
                self.stdout.write(
                    f"\nVocê está prestes a MOVER {len(old_sales)} personagens\n"
                    f"para a conta mestre e manter as vendas ativas.\n"
                )
            else:
                self.stdout.write(
                    f"\nVocê está prestes a CANCELAR {len(old_sales) + len(missing_chars)} vendas antigas.\n"
                    f"Os personagens permanecerão nas contas atuais.\n"
                )
            
            confirm = input("\nDigite 'SIM' para confirmar: ")
            if confirm != 'SIM':
                self.stdout.write(self.style.ERROR('\n❌ Operação cancelada pelo usuário.\n'))
                return

        # Executa as ações
        cancelled_count = 0
        moved_count = 0
        error_count = 0

        self.stdout.write(self.style.WARNING(
            f"\n{'='*70}\n"
            f"  🔄 PROCESSANDO...\n"
            f"{'='*70}\n"
        ))

        # Cancela vendas de personagens não encontrados
        for sale in missing_chars:
            try:
                with transaction.atomic():
                    sale.status = 'cancelled'
                    sale.save()
                    cancelled_count += 1
                    self.stdout.write(self.style.SUCCESS(
                        f"✅ Venda #{sale.id} ({sale.char_name}) - CANCELADA (personagem não existe)"
                    ))
            except Exception as e:
                error_count += 1
                self.stdout.write(self.style.ERROR(
                    f"❌ Erro ao cancelar venda #{sale.id}: {str(e)}"
                ))

        # Processa vendas antigas
        for sale, current_account in old_sales:
            try:
                with transaction.atomic():
                    if move_to_master:
                        # Move para conta mestre
                        success = LineageMarketplace.transfer_character_to_account(
                            sale.char_id,
                            MARKETPLACE_MASTER_ACCOUNT
                        )
                        if success:
                            moved_count += 1
                            self.stdout.write(self.style.SUCCESS(
                                f"✅ Venda #{sale.id} ({sale.char_name}) - MOVIDO para conta mestre"
                            ))
                        else:
                            raise Exception("Falha ao transferir personagem")
                    else:
                        # Cancela a venda
                        sale.status = 'cancelled'
                        sale.save()
                        cancelled_count += 1
                        self.stdout.write(self.style.SUCCESS(
                            f"✅ Venda #{sale.id} ({sale.char_name}) - CANCELADA"
                        ))
            except Exception as e:
                error_count += 1
                self.stdout.write(self.style.ERROR(
                    f"❌ Erro ao processar venda #{sale.id} ({sale.char_name}): {str(e)}"
                ))

        # Relatório final
        self.stdout.write(self.style.SUCCESS(
            f"\n{'='*70}\n"
            f"  📊 RELATÓRIO FINAL\n"
            f"{'='*70}\n"
        ))
        
        if move_to_master:
            self.stdout.write(self.style.SUCCESS(
                f"✅ Personagens movidos para conta mestre: {moved_count}"
            ))
        
        self.stdout.write(self.style.SUCCESS(
            f"✅ Vendas canceladas: {cancelled_count}"
        ))
        
        if error_count > 0:
            self.stdout.write(self.style.ERROR(
                f"❌ Erros encontrados: {error_count}"
            ))
        
        self.stdout.write(self.style.SUCCESS(
            f"\n{'='*70}\n"
            f"  ✅ PROCESSO CONCLUÍDO\n"
            f"{'='*70}\n"
        ))

