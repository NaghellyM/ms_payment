from flask import Flask, request, jsonify
import os
import json
from dotenv import load_dotenv
from epaycosdk.epayco import Epayco
import requests

load_dotenv()

app = Flask(__name__)

# Instancia Epayco
epayco = Epayco({
    'apiKey': os.getenv('EPAYCO_PUBLIC_KEY'),
    'privateKey': os.getenv('EPAYCO_PRIVATE_KEY'),
    'lenguage': 'ES',
    'test': os.getenv('EPAYCO_TEST') == 'true',
})

# Método para verificar la existencia de invoice_reference en otro microservicio
def invoice_reference(invoice_reference):
    try:
        # Validar la referencia de la factura con el microservicio de negocio
        url = f"{os.getenv('MS_BUSINESS_URL')}/invoices/{invoice_reference}"
        response = requests.get(url)
        
        if response.status_code == 200 and response.json().get('invoice'):
            return response.json().get('invoice_reference')
        else:
            return {'error': 'La referencia de la factura no es válida o no existe.'}
    except Exception as e:
        return {'error': f'Error de conexión: {str(e)}'}


# Método para el token de la tarjeta
def create_token(data):
    try:
        card_info = {
            "card[number]": data['card_number'],
            "card[exp_year]": data['exp_year'],
            "card[exp_month]": data['exp_month'],
            "card[cvc]": data['cvc'],
            "hasCvv": True
        }
        return epayco.token.create(card_info)
    except Exception as e:
        return {'error': str(e)}

# Método para crear un cliente
def create_customer(token, data):
    customer_info = {
        'name': data['name'],
        'last_name': data['last_name'],
        'email': data['email'],
        'phone': data['phone'],
        'default': True,
        'token_card': token
    }
    try:
        return epayco.customer.create(customer_info)
    except Exception as e:
        return {'error': str(e)}

# Método para procesar el pago
def process_payment(data, customer_id, token_card):
    try:
        payment_info = {
            'token_card': token_card,
            'customer_id': customer_id,
            'doc_type': "CC",
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
            'currency': 'COP',
            'invoice_reference': data['invoice_reference']
        }
        return epayco.charge.create(payment_info)
    except Exception as e:
        return {'error': str(e)}

# Endpoint para manejar todo el flujo de pago
@app.route('/process_payment', methods=['POST'])
def handle_process_payment():
    data = request.json

    # Verificar la referencia de la factura
    invoice_ref_check = invoice_reference(data['invoice_reference'])

    # Validar si la referencia es None
    if invoice_ref_check is None or 'error' in invoice_ref_check:
        error_message = invoice_ref_check if invoice_ref_check else {'error': 'No se obtuvo respuesta del microservicio de negocio'}
        return jsonify(error_message), 400

    # Crear token de tarjeta
    token_response = create_token(data)
    if token_response.get("status") is False:
        return jsonify({'error': 'Error al crear token', 'details': token_response}), 500

    token_card = token_response['id']

    # Crear cliente
    customer_response = create_customer(token_card, data)
    if 'error' in customer_response:
        return jsonify({'error': 'Error al crear cliente', 'details': customer_response}), 500

    customer_id = customer_response['data']['customerId']

    # Procesar pago
    payment_response = process_payment(data, customer_id, token_card)
    if payment_response.get('status') is True and payment_response.get('data', {}).get('estado') == 'Aceptada':
        return jsonify({
            'status': 'success',
            'message': 'Pago realizado con éxito',
            'transaction_id': payment_response['data']['ref_payco'],
            'details': payment_response['data']
        }), 200
    else:
        return jsonify({
            'status': 'error',
            'message': 'No se pudo procesar el pago',
            'details': payment_response
        }), 500


if __name__ == '__main__':
    app.run(debug=True)
