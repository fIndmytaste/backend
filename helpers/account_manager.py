import logging, traceback

from account.models import Vendor



class AccountManager:

    def __init__(self,request) -> None:
        self.request = request

    def save_bank_details(self, user, bank_name: str, account_number: str, account_name: str):
        """Persist bank details for any payee -- rider, vendor or buyer.

        The User row is the canonical place: it is what the wallet falls back
        to and the only place a rider has. A Vendor row, when one exists, is
        mirrored so vendor payouts keep reading their own copy.

        This used to require a Vendor and take it as its only argument, so
        riders -- who have no Vendor row -- could never save a bank account at
        all. The failure surfaced as the generic "an error occurred" message,
        and left the rider's payout details permanently blank.
        """
        try:
            user.bank_account = account_number
            user.bank_name = bank_name
            user.bank_account_name = account_name
            user.save(update_fields=['bank_account', 'bank_name', 'bank_account_name'])

            vendor = Vendor.objects.filter(user=user).first()
            if vendor:
                vendor.bank_account = account_number
                vendor.bank_name = bank_name
                vendor.bank_account_name = account_name
                vendor.save(update_fields=['bank_account', 'bank_name', 'bank_account_name'])

            return True, 'Bank account detail successfully updated'
        except Exception as e:
            logging.error(e)
            logging.error(traceback.print_exc())
            return False, 'An error occurred while adding bank account detail'
        





    

    




