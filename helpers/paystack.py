from decimal import Decimal
import json
import requests
from findmytaste import settings
from account.models import Vendor, VirtualAccount
from django.urls import reverse

from helpers.response.response_format import bad_request_response, success_response, internal_server_error_response
from wallet.models import Wallet, WalletTransaction




class PaystackManager:


    def __init__(self) -> None:
        header = {
            'Authorization': f'Bearer sk_live_9ed4dc5cefb81af819a77ddb567feae183546471',
            'Content-Type': 'application/json',
        }
        self.header = header
        self.base_url = "https://api.paystack.co"


    def get_header(self):
        header = {
            'Authorization': f'Bearer sk_live_9ed4dc5cefb81af819a77ddb567feae183546471',
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
        response = requests.get(f'{self.base_url}/banks', headers=self.get_header())
        print(response.text)
        if response.ok:
            banks = response.json()['data']
            print(banks)
            exist = list(filter(lambda x: x.get('code') == bank_code, banks))
            if not exist:
                return False , 'Invalid bank provided'
            return True , exist[0]
        return False , 'Unable to verify bank'
    

    def verify_transaction(self,transaction_id):
        response = requests.get('https://api.flutterwave.com/v3/transactions/{}/verify'.format(transaction_id), headers=self.get_header())
        if response.status_code == 200:
            return True , response.json()
        return False , 'Payment is not successful'


    def create_virtual_customer(self,first_name, last_name, email, phone ):
        url = f'{self.base_url}/customer'
        payload = json.dumps({
            'first_name':first_name,
            'last_name':last_name,
            'email':email,
            'phone':phone
        })
        response = requests.post(url, headers=self.get_header(), data=payload)
        
        if response.ok:
            return True , response.json()['data']
        
        print(response.text)
        return False , "Account could not be resolve"
    
    def create_virtual_account(self,customer_ref):
        url = f'{self.base_url}/dedicated_account'
        payload = json.dumps({
            'customer':customer_ref,
            'preferred_bank':'wema-bank',
        })
        response = requests.post(url, headers=self.get_header(), data=payload)
        
        if response.ok:
            return True , response.json()['data']
        print(response.text)
        return False , "Account could not be resolve"
    


    def resolve_bank_account(self,account_number,bank_code):
        url = f'{self.base_url}/bank/resolve?account_number={account_number}&bank_code={bank_code}'
        print(self.get_header() )
        response = requests.get(url, headers=self.get_header())
        print(response.text)
        if response.ok:
            return True , response.json()['data']
        return False , "Account could not be resolve"

    

    def banks(self):
        url = f'{self.base_url}/bank'
        print(self.get_header() )
        response = requests.get(url, headers=self.get_header())
        print(response.text)
        if response.ok:
            return True , response.json()['data']
        return False , "Account could not be resolve"

    


    def handle_webhook(self,request):
        payload = request.data
        event_type = payload.get("event")

        if event_type == "charge.success":
            try:
                data = payload.get('data')
                status = data.get("status")
                if status == "success":
                    # check if transaction has been proccessed
                    reference = data.get('reference')
                    trx_extist = WalletTransaction.objects.filter(external_reference=reference).first()
                    if trx_extist:
                        return bad_request_response(
                            message="Transaction already processed"
                        )
                
                    amount = data.get("amount")
                    process_amount = Decimal(amount / 100)
                    metadata = data.get('metadata',{})
                    if metadata:
                        receiver_account_number = metadata.get('receiver_account_number')
                        v_account = VirtualAccount.objects.filter(account_number=receiver_account_number).first()
                        if v_account:
                            wallet = Wallet.objects.get(user=v_account.user)

                            WalletTransaction.objects.create(
                                wallet=wallet,
                                amount=Decimal(process_amount),
                                transaction_type='deposit',
                                external_reference=reference,
                                status='completed',
                                response_data=payload,
                                description = "Deposit from bank"
                            )

                            # update the user wallet balance
                            wallet.balance += process_amount
                            wallet.save()
                            return success_response(
                                message="Transaction processed successfully"
                            )
                
            except:
                return internal_server_error_response() 
        return success_response()



