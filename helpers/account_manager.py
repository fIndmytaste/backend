import logging, traceback

from account.models import Vendor



class AccountManager:

    def __init__(self,request) -> None:
        self.request = request

    def add_bank_account(self, vendor:Vendor,  bank_name:str,account_number:str,account_name:str):
        try:
            vendor.bank_account = account_number
            vendor.bank_name = bank_name
            vendor.bank_account_name = account_name
            vendor.save()
            user = vendor.user
            user.bank_account = account_number
            user.bank_name = bank_name
            user.bank_account_name = account_name
            user.save()
            return True , 'Bank account detail successfully updated'
        except Exception as e:
            logging.error(e)
            logging.error(traceback.print_exc())
            return False, 'An error occurred while adding bank account detail'
        





    

    




