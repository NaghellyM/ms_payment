from flask import Flask, request, jsonify
import os
import json
from dotenv import load_dotenv
from epaycosdk.epayco import Epayco
import requests


load_dotenv()#carga las variables de entorno que estan en el archivo .env

app = Flask(__name__) # Esta instancia se utiliza para configurar y ejecutar la aplicación web

# Instancia la clase Epayco con las credenciales de la cuenta
epayco = Epayco({
    'apiKey': os.getenv('EPAYCO_PUBLIC_KEY'),
    'privateKey': os.getenv('EPAYCO_PRIVATE_KEY'),
    'lenguage': 'ES', #lenjuage de los mensajes
    'test': os.getenv('EPAYCO_TEST') == 'true', #"Aqui hay un cambio" "#definir de modo de prueba a produccion

})


#metodo para el token de la tarjeta
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

    #metodo para crear un cliente
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
    
    # Método para obtener la invoice_reference desde el microservicio de negocio
def get_invoice_reference(invoice_reference):
    try:
        # Hacer una solicitud HTTP al microservicio para obtener la referencia de la factura
        url = f"{os.getenv('MS_BUSINESS_URL')}/createMSP/{id}"
        response = requests.get(url)
        
        if response.status_code == 200:
            return response.json().get('invoice_reference')
        else:
            return None
    except Exception as e:
        return None

def process_payment(data, customer_id, token_card):
    try:
        payment_info = {
            'token_card': token_card,
            'customer_id': customer_id,
            "doc_type": "CC",
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
       
        response = epayco.charge.create(payment_info)
        print("Payment Response:", json.dumps(response, indent=4))  # Agregar detalles para debug

        # Validar el estado de la transacción
        if response.get('status') is True and response.get('data', {}).get('estado') == 'Aceptada':
            return {
                'status': 'success',
                'message': 'Pago realizado con éxito',
                'transaction_id': response['data']['ref_payco'],
                'details': response['data']
            }
        else:
            return {
                'status': 'failed',
                'message': 'Pago fallido',
                'error': response.get('data', {}).get('description', 'No se pudo procesar el pago'),
                'details': response['data']
            }

    except Exception as e:
        return {'error': str(e)}



#enpoint para manejar todo el flujo de pago
@app.route('/proces_payment', methods=['POST'])
def handle_process_payment():
    data = request.json

#crea el token de la tarjeta
    token_response = create_token(data)
    print("Token response", json.dumps(token_response))

#verificar si hubo error al crear el token
    if token_response["status"] is False:
        return jsonify(token_response), 500

    token_card = token_response['id'] #extrae el id del token

    #Crear cliente
    customer_response = create_customer(token_card, data)
    print("Customer response", json.dumps(customer_response))

    #Verificar si hubo error al crear el cliente
    if 'error' in customer_response:
        return jsonify(customer_response), 500

    customer_id = customer_response['data']['customerId']

    #Procesar el pago
    payment_response = process_payment(data, customer_id, token_card)
    print("Payment Response:", json.dumps(payment_response, indent=4))

    if payment_response.get('status') == 'success':
        return jsonify(payment_response), 200
    else:
        return jsonify({
        'status': 'error',
        'message': 'Hubo un problema al procesar el pago',
        'details': payment_response
    }), 500



if __name__ == '__main__':
    app.run(debug=True)
