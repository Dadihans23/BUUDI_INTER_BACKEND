"""
Management command : réconciliation automatique des transferts bloqués.

Usage :
    python manage.py reconcile_transfers
    python manage.py reconcile_transfers --hours 2   # transferts bloqués depuis > 2h
    python manage.py reconcile_transfers --dry-run   # simulation sans écriture

Ce que ça fait :
  1. Prend tous les Transfer en statut 'disbursing' depuis plus de X heures
  2. Appelle check_status Paydunya pour chacun
  3. Met à jour le statut en base selon la réponse
  4. Affiche un rapport

À lancer en cron job en prod (ex: toutes les heures).
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger('buudi')


class Command(BaseCommand):
    help = 'Réconcilie les transferts en statut disbursing depuis trop longtemps avec Paydunya'

    def add_arguments(self, parser):
        parser.add_argument(
            '--hours', type=int, default=1,
            help='Seuil en heures pour considérer un transfert comme bloqué (défaut: 1)'
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Simulation : affiche ce qui serait fait sans modifier la base'
        )

    def handle(self, *args, **options):
        from transfers.models import Transfer
        from paydunya.client import PayDunyaClient

        hours    = options['hours']
        dry_run  = options['dry_run']
        seuil    = timezone.now() - timedelta(hours=hours)

        transferts = Transfer.objects.filter(
            status='disbursing',
            updated_at__lt=seuil
        ).order_by('updated_at')

        total = transferts.count()

        if total == 0:
            self.stdout.write(self.style.SUCCESS(
                f'✅ Aucun transfert bloqué depuis > {hours}h. Tout est propre.'
            ))
            return

        self.stdout.write(self.style.WARNING(
            f'🔍 {total} transfert(s) disbursing depuis > {hours}h — vérification en cours...'
        ))
        if dry_run:
            self.stdout.write(self.style.WARNING('  [DRY RUN — aucune modification en base]'))

        client  = PayDunyaClient()
        success = failed = pending = errors = 0

        for t in transferts:
            if not t.disburse_token:
                self.stdout.write(f'  ⚠️  Transfer #{t.id} : pas de token → ignoré')
                errors += 1
                continue

            try:
                check = client.check_status(t.disburse_token)
            except Exception as e:
                self.stdout.write(f'  ❌ Transfer #{t.id} : erreur réseau → {e}')
                errors += 1
                continue

            if check.get('response_code') != '00':
                self.stdout.write(
                    f'  ❌ Transfer #{t.id} : Paydunya erreur → {check.get("response_text", check)}'
                )
                errors += 1
                continue

            raw = check.get('status', 'pending')

            if raw == 'success':
                self.stdout.write(self.style.SUCCESS(f'  ✅ Transfer #{t.id} → SUCCESS'))
                if not dry_run:
                    t.status = 'success'
                    t.save(update_fields=['status'])
                success += 1

            elif raw == 'failed':
                self.stdout.write(self.style.ERROR(f'  ❌ Transfer #{t.id} → CREDIT_FAILED'))
                if not dry_run:
                    t.status = 'credit_failed'
                    t.save(update_fields=['status'])
                failed += 1

            elif raw == 'created':
                # Submit n'a pas abouti → re-soumettre
                self.stdout.write(f'  🔄 Transfer #{t.id} → created, re-submit...')
                if not dry_run:
                    try:
                        client.disburse_submit(t.disburse_token, t.disburse_id)
                    except Exception:
                        pass
                pending += 1

            else:
                self.stdout.write(f'  ⏳ Transfer #{t.id} → toujours {raw}')
                pending += 1

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'📊 Résultat : {success} success | {failed} credit_failed | '
            f'{pending} toujours pending | {errors} erreurs'
        ))
        logger.info(
            f'RECONCILIATION → {total} transferts vérifiés → '
            f'{success} success, {failed} failed, {pending} pending, {errors} erreurs'
        )
