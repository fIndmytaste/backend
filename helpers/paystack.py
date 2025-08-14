from decimal import Decimal
import json
import requests
from findmytaste import settings
from account.models import User, Vendor, VirtualAccount
from helpers.response.response_format import bad_request_response, success_response, internal_server_error_response
from wallet.models import Wallet, WalletTransaction




class PaystackManager:


    def __init__(self) -> None:
        header = {
            'Authorization': f'Bearer {settings.PAYSTACK_SECRET_KEY}',
            'Content-Type': 'application/json',
        }
        self.header = header
        self.base_url = "https://api.paystack.co"


    def get_header(self):
        header = {
            'Authorization': f'Bearer {settings.PAYSTACK_SECRET_KEY}',
            'Content-Type': 'application/json',
        }
        print(header)
        return header

    
    def make_withdrawal(self, request, vendor: Vendor, amount, transaction_obj):
        account_bank = None
        account_number = None
        if vendor and vendor.bank_name and vendor.bank_account_name:
            account_bank = vendor.bank_name
            account_number = vendor.bank_account_name
        else:
            if not (request.data.get('bank_code') and request.data.get('account_number')):
                return bad_request_response(message='You did not have an account attached to your profile, kindly add.')
            account_bank = request.data['bank_code']
            account_number = request.data['account_number']

        # Resolve bank account to get recipient code
        is_valid, resolve_result = self.resolve_bank_account(account_number, account_bank)
        if not is_valid:
            return bad_request_response(message=resolve_result)

        # Create transfer recipient
        recipient_data = {
            "type": "nuban",
            "name": vendor.bank_account_name if vendor else "Withdrawal Recipient",
            "account_number": account_number,
            "bank_code": account_bank,
            "currency": "NGN"
        }
        recipient_response = requests.post(
            f'{self.base_url}/transferrecipient',
            headers=self.get_header(),
            json=recipient_data
        )
        if not recipient_response.ok:
            return bad_request_response(message='Failed to create transfer recipient')

        recipient_code = recipient_response.json()['data']['recipient_code']

        # Initiate transfer
        data = {
            "source": "balance",
            "amount": int(amount * 100),  # Convert to kobo
            "recipient": recipient_code,
            "reason": "Withdrawal from balance",
            "reference": str(transaction_obj.id)
        }
        response = requests.post(
            f'{self.base_url}/transfer',
            headers=self.get_header(),
            json=data
        )

        if response.ok:
            initiate_result = response.json()
            if initiate_result['status'] == 'success':
                transaction_obj.response_data = initiate_result
                transaction_obj.status = 'pending'  # Paystack transfers may need webhook confirmation
                transaction_obj.save()
                return success_response(message='Withdrawal initiated successfully')
            else:
                return bad_request_response(message='Withdrawal creation failed')
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
        print(transaction_id)
        print(transaction_id)
        print(transaction_id)
        response = requests.get(f'{self.base_url}/transaction/verify/{transaction_id}', headers=self.get_header())
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
        
        
        
        elif event_type == "transfer.success":
            try:
                data = payload.get('data')
                reference = data.get('reference')
                transaction = WalletTransaction.objects.filter(id=reference, transaction_type='withdrawal').first()
                if transaction and transaction.status != 'completed':
                    transaction.status = 'completed'
                    transaction.response_data = payload
                    transaction.save()
                    return success_response(message="Withdrawal confirmed successfully")
                return bad_request_response(message="Transaction already processed or not found")
            except Exception:
                return internal_server_error_response()

        elif event_type == "transfer.failed":
            try:
                data = payload.get('data')
                reference = data.get('reference')
                transaction = WalletTransaction.objects.filter(id=reference, transaction_type='withdrawal').first()
                if transaction:
                    transaction.status = 'failed'
                    transaction.response_data = payload
                    transaction.save()
                    # Optionally refund the wallet
                    wallet = transaction.wallet
                    wallet.deposit(transaction.amount)
                    return bad_request_response(message="Withdrawal failed and amount refunded")
                return bad_request_response(message="Transaction not found")
            except Exception:
                return internal_server_error_response()
        
        return success_response()


    
    
    def initiate_payment(self, request, amount,order, is_mobile=False):

        try:
            user : User = request.user
            user_id = str(user.id)
            # uuidb64 = urlsafe_base64_encode(force_bytes(user_id))
            # reference = f'ref_{uuidb64}_{uuid4().hex}' 
            url = f"{self.base_url}/transaction/initialize"
            transaction = WalletTransaction.objects.create(
                user=user,
                amount=amount,
                order=order,
                transaction_type='purchase'
            )

            new_amount = amount * 100

            metadata = {
                "user_id": user_id,
                "name": user.full_name,
                "email": user.email,
                "amount": str(new_amount),
                "reference": str(transaction.id),
                "payment_type": 'order-payment',
                "payment_mode": 'website-link',
            }


            if is_mobile:
                metadata['payment_mode'] =  'mobile-payment'
                response_data = dict(
                    metadata=metadata
                )
                return success_response(data=response_data)

            payload = json.dumps({
                "amount": float(new_amount),
                "email": user.email,
                "callback_url": request.data.get("callback_url"),
                "cancel_url": request.data.get("callback_url"), 
                "channels": ['card'],
                "currency": "NGN",
                "metadata": metadata
            })
            response = requests.request("POST", url, headers=self.get_header(), data=payload)
            if response.ok:
                resp = response.json().get("data")
                transaction.external_reference = resp.get('reference')
                transaction.save()
                new_response = dict(url=resp.get("authorization_url"))
                return success_response(data=new_response)
            else:
                return bad_request_response(message="Card tokenization can't be completed at the moment")

        except Exception as e:
            print(e)
            return internal_server_error_response()

