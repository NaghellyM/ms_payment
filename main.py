from flask import Flask, request, jsonify
import os
import json
from dotenv import load_dotenv
from epaycosdk.epayco import Epayco


load_dotenv()#carga las variables de entorno que estan en el archivo .env

app = Flask(__name__) # Esta instancia se utiliza para configurar y ejecutar la aplicación web

# Instancia la clase Epayco con las credenciales de la cuenta
epayco = Epayco({
    'apiKey': os.getenv('EPAYCO_PUBLIC_KEY'),
    'privateKey': os.getenv('EPAYCO_PRIVATE_KEY'),
    'lenguage': 'ES', #lenjuage de los mensajes
    'test': os.getenv('EPAYCO_TEST') == 'true', #"Aqui hay un cambio" "#definir de modo de prueba a produccion

})

if __name__ == '__main__':
    app.run(debug=True)

def create_token(data):
    try:
        card_info = {
            "card[number]": data['card_number'],
            "card[exp_year]":data['exp_year'],
            "card[exp_month]": data['exp_month'],
            "card[cvc]": data['cvc'],
            "hasCvv": True  # hasCvv: validar codigo de seguridad en la transacción
        }
        token = epayco.token.create(card_info)
        return token
    except Exception as e:
        return {'error': str(e)}
def create_customer(token,data):
    customer_info={
        'name': data['name'],
        'last_name':data['last_name'],
        'email':data['email'],
        'phone' : data['phone'],
        'default': True
    }
    customer_info['token_card'] = token
    try:
        customer = epayco.customer.create(customer_info)
        return customer
    except Exception as e:
        return {'error': str(e)}
def process_payment(data, customer_id, token_card):
    try:
        payment_info = {
            'token_card': token_card,
            'customer_id': customer_id,
            "doc_type": "CC",  # Incluye 'doc_type' aquí
            'doc_number': data['doc_number'],
            'name': data['name'],
            'last_name': data['last_name'],
            'email': data['email'],
            'city': data['city'],
            'address': data['address'],
            'phone': data['phone'],
            'cell_phone': data['cell_phone'],
            'bill': data['bill'],
            'description': 'Pago de servicios',
            'value': data['value'],
            'tax': '0',
            'tax_base': data['value'],
            'currency': 'COP'

        }
        print(f"Payment Info: {json.dumps(payment_info, indent=4)}")  # Imprime los datos de la solicitud

        response = epayco.charge.create(payment_info)
        return response
    except Exception as e:
        return {'error': str(e)}
