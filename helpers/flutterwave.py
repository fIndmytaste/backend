import requests
from findmytaste import settings
from account.models import Vendor
from django.urls import reverse

from helpers.response.response_format import bad_request_response, success_response




class FlutterwaveManager:


    def __init__(self) -> None:
        header = {
            'Authorization': f'Bearer {settings.FLUTTERWAVE_AUTH_TOKEN}',
            'Content-Type': 'application/json',
        }
        self.header = header


    def get_header(self):
        header = {
            'Authorization': f'Bearer {settings.FLUTTERWAVE_AUTH_TOKEN}',
            'Content-Type': 'application/json',
        }
        return header

    
    def make_withdrawal(self,request,vendor:Vendor,amount, transaction_obj):
        account_bank = None
        account_number = None
        print(vendor.bank_name , vendor.bank_account_name)
        if vendor.bank_name and vendor.bank_account_name:
            account_bank = vendor.bank_name
            account_number = vendor.bank_account_name
        else:

            if any([ request.data.get('bank_code') in [None,False] , request.data.get('account_number') in [None,False] ]):
                return bad_request_response(message='You did not have an account attached to your profile, kindly add.')

            account_bank = request.data['bank_code']
            account_number = request.data['account_number']

        data = {
            "account_bank": account_bank,
            "account_number":  account_number,
            "amount": amount,
            "narration": "Withdrawal from balance",
            "currency": "NGN",
            "reference": f"{transaction_obj.uuid}_PMCKDU_1", #!TODO make sure this is actual transaction ref from DB
            # "callback_url": 'https://play.svix.com/in/e_6O0J7HodDYMurpXRzPcf7UBWxOO/'
            "callback_url": request.build_absolute_uri(reverse("flutterwave-withdrawal-callback"))
        }

        response = requests.post('https://api.flutterwave.com/v3/transfers', headers=self.get_header(), json=data)
        print(response)
        print(response.text)
        if response.ok:
            initiate_result = response.json()
            if initiate_result['status'] != 'success':
                return bad_request_response(message='Withdrawal creation failed')
            transaction_obj.response = initiate_result
            transaction_obj.save()
            return success_response(message='Withdrawal completed')
        
        else:
            return bad_request_response(message='Withdrawal creation failed')
    

    def validate_bank(self,bank_code):
        response = requests.get('https://api.flutterwave.com/v3/banks/NG', headers=self.get_header())
        if response.ok:
            banks = response.json()['data']
            exist = list(filter(lambda x: x.get('code') == bank_code, banks))
            if not exist:
                return False , bad_request_response(message='Invalid bank provided')

            return True , exist[0]
        return False , bad_request_response(message='Unable to verify bank',status_code=500)

    def verify_transaction(self,transaction_id):
        response = requests.get('https://api.flutterwave.com/v3/transactions/{}/verify'.format(transaction_id), headers=self.get_header())
        if response.status_code == 200:
            return True , response.json()
        return False , 'Payment is not successful'


    def resolve_bank_account(self,account_number,account_bank, bank_name):
        payload = {
            "account_number": account_number,
            "account_bank": account_bank
        }
        response = requests.post('https://api.flutterwave.com/v3/accounts/resolve', headers=self.get_header(),json=payload )
        if response.ok:
            return True , response.json()['data']
        return False , bad_request_response(message=f"Inavlid account number for {bank_name}")

    
    def handle_webhook(self,request):
        payload = request.data
        event_type = payload.get("event")

        if event_type.lower() == 'transfer':
            my_transaction_id = payload.get("transfer", {}).get("reference")
            transfer_data = payload.get("transfer", {})
            try:
                my_transaction_id = my_transaction_id.split('_PMCKDU_1')[0] #!! this is jus for testing purpose
                transaction = Transaction.objects.get(uuid=my_transaction_id)
            except Exception as e:
                print(e)
                return bad_request_response(message='Invalid transaction reference')
            
            if transfer_data.get('status','').upper() == 'SUCCESSFUL':
                transaction.status = 'success'
                transaction.response = payload
                transaction.save()

            elif transfer_data.get('status','').upper() == 'FAILED':
                # revert vendor money
                try:
                    transaction.status = 'failed'
                    transaction.response = payload
                    vendor = Vendor.objects.get(id=transaction.vendor.id)
                    new_balance = vendor.account_balance + transaction.amount
                    vendor.account_balance = new_balance
                    transaction.save()
                    vendor.save()
                except:
                    pass
                


        return success_response()



