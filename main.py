from flask import Flask, request, jsonify
import os
import json
from dotenv import load_dotenv
from epaycosdk.epayco import Epayco
import requests
from flask_cors import CORS

load_dotenv()  # carga las variables de entorno que estan en el archivo .env

app = Flask(__name__)  # Esta instancia se utiliza para configurar y ejecutar la aplicación web
CORS(app)  # Esto permite todas las solicitudes de cualquier origen

# Instancia la clase Epayco con las credenciales de la cuenta
epayco = Epayco({
    'apiKey': os.getenv('EPAYCO_PUBLIC_KEY'),
    'privateKey': os.getenv('EPAYCO_PRIVATE_KEY'),
    'lenguage': 'ES',  # lenjuage de los mensajes
    'test': os.getenv('EPAYCO_TEST') == 'true',  # "Aqui hay un cambio" "#definir de modo de prueba a produccion

})


def get_quota_details(data):
    try:
        quota_id = data.get('quota_id')
        if not quota_id:
            return {
                'success': False,
                'error': 'El ID de la factura es requerido'
            }

        # Hacer la petición al MS de negocios
        business_ms_base_url = os.getenv('MS_BUSINESS')
        business_ms_url = f"{business_ms_base_url}/quotas/{quota_id}"

        response = requests.get(business_ms_url)
        print("Respuesta del microservicio:", response.status_code, response.text)

        if response.status_code == 200: 
            quota_data = response.json()
            print(f"Datos recibidos de la factura: {quota_data}")

            # if 'quota' not in quota_data:
            #     return {
            #         'success': False,
            #         'error': 'No se encontró la clave "quota" en la respuesta del microservicio'
            #     }

            return {
                'success': True,
                # 'quota': quota_data['quota'],
                'amount': quota_data['amount']
            }
        else:
            return {
                'success': False,
                'error': 'No se pudo obtener la información de la factura'
            }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }



# metodo para el token de la targeta
def create_token(data):
    try:
        card_info = {
            "card[number]": data['card_number'],
            "card[exp_year]": data['exp_year'],
            "card[exp_month]": data['exp_month'],
            "card[cvc]": data['cvc'],
            "hasCvv": True  # hasCvv: validar codigo de seguridad en la transacción
        }
        token = epayco.token.create(card_info)
        return token
    except Exception as e:
        return {'error': str(e)}

    # metodo para crear un cliente


def create_customer(token, data):
    customer_info = {
        'name': data['name'],
        'last_name': data['last_name'],
        'email': data['email'],
        'phone': data['phone'],
        'default': True
    }
    customer_info['token_card'] = token
    try:
        customer = epayco.customer.create(customer_info)
        return customer
    except Exception as e:
        return {'error': str(e)}


def process_payment(data, customer_id, token_card, quota_data):
    print(quota_data, "hola")
    print("aqui estoy", quota_data['amount'])
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
            # 'bill': data['bill'],
            'description': f'Pago de factura {data["quota_id"]}',
            # 'description': 'Pago de servicios',
            # 'value': data['value'],
            'value': str(quota_data['amount']),
            'tax': '0',
            'tax_base': str(quota_data['amount']),
            # 'tax_base': data['value'],
            'currency': 'COP'

}
        print(f"Payment Info: {json.dumps(payment_info, indent=4)}")  # Imprime los datos de la solicitud

        # aqui es donde se hace el llmado a la funcion que envia el pago al correo
        response = epayco.charge.create(payment_info)  # Realiza la solicitud de pago

        if response.get('status') is True:
            update_quota_status(data['quota_id'], response.get('data', {}))
            print("ACTUALIZAR")
        response = epayco.charge.create(payment_info)
        return response
    except Exception as e:
        return {'error': str(e)}


def update_quota_status(quota_id, payment_data):
    try:
        update_url = f"http://127.0.0.1:3333/quotas/{quota_id}"
        update_data = {
            # "payment_status": "PAID",
            # "payment_reference": payment_data.get('ref_payco'),
            # "payment_date": payment_data.get('transaction_date'),
            "status": True
        }

        response = requests.put(update_url, json=update_data)
        return response.status_code == 200
    except Exception as e:
        print(f"Error actualizando factura: {str(e)}")
        return False


# enpoint para manejar todo el flujo de pago
@app.route('/process_payment', methods=['POST'])
def handle_process_payment():
    try:
        data = request.json

        # Validar datos requeridos
        required_fields = ['quota_id', 'card_number', 'exp_year', 'exp_month', 'cvc',
                           'name', 'last_name', 'email', 'doc_number', 'city', 'address',
                           'phone', 'cell_phone']

        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"El campo {field} es requerido"}), 400

        # Obtener detalles de la factura
        quota_response = get_quota_details(data)
        if not quota_response['success']:
            return jsonify({"error": quota_response['error']}), 400

        # Crear token de tarjeta
        token_response = create_token(data)
        print("Token response:", json.dumps(token_response))

        if not token_response.get('status'):
            return jsonify({"error": "Error creando token de tarjeta",
                            "details": token_response.get('error')}), 500

        token_card = token_response['id']

        # Crear cliente
        customer_response = create_customer(token_card, data)
        print("Customer response:", json.dumps(customer_response))

        if 'error' in customer_response:
            return jsonify({"error": "Error creando cliente",
                            "details": customer_response['error']}), 500

        customer_id = customer_response['data']['customerId']

        # Procesar pago
        payment_response = process_payment(data, customer_id, token_card, quota_response)
        print("Payment response:", json.dumps(payment_response))

        if 'error' in payment_response:
            return jsonify({"error": "Error procesando pago",
                            "details": payment_response['error']}), 500

        return jsonify({
            "status": "success",
            "message": "Pago procesado correctamente",
            "data": payment_response
        }), 200

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": "Error procesando el pago",
            "error": str(e)
        }), 500


if __name__ == '__main__':
    app.run(debug=True)