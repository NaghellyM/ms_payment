from flask import Flask, request, jsonify
import os
import json
from dotenv import load_dotenv
from epaycosdk.epayco import Epayco
import requests

load_dotenv()  # carga las variables de entorno que estan en el archivo .env

app = Flask(__name__)  # Esta instancia se utiliza para configurar y ejecutar la aplicación web

# Instancia la clase Epayco con las credenciales de la cuenta
epayco = Epayco({
    'apiKey': os.getenv('EPAYCO_PUBLIC_KEY'),
    'privateKey': os.getenv('EPAYCO_PRIVATE_KEY'),
    'lenguage': 'ES',  # lenjuage de los mensajes
    'test': os.getenv('EPAYCO_TEST') == 'true',  # "Aqui hay un cambio" "#definir de modo de prueba a produccion

})


def get_invoice_details(data):
    try:
        invoice_id = data.get('invoice_id')
        if not invoice_id:
            return {
                'success': False,
                'error': 'El ID de la factura es requerido'
            }

        # Hacer la petición al MS de negocios

        # Obtener la URL base del microservicio desde las variables de entorno
        business_ms_base_url = os.getenv('MS_BUSINESS')

        # Construir la URL completa
        business_ms_url = f"{business_ms_base_url}/invoices/{invoice_id}"
        # response = requests.post(business_ms_url, json={'id': invoice_id})
        response = requests.get(business_ms_url)
        print(response)

        if response.status_code == 200:  # Verifica si la respuesta HTTP tiene un código de estado 200 (OK)
            invoice_data = response.json()  # respuesta JSON en un diccionario de Python
            print(f"Respuesta de la factura: {invoice_data}")  # Imprime la respuesta JSON para depuración
            print(f"total: {invoice_data['invoice']['total']} ")  # Imprime el valor del campo 'total' de la factura
            if 'total' not in invoice_data['invoice']:  # Verifica si el campo 'total' está presente en la respuesta
                return {
                    'success': False,
                    'error': 'La respuesta no contiene el campo "total"'
                }
            return {
                # Si el campo 'total' está presente, retorna un diccionario con los detalles de la factura y el total
                'success': True,
                'invoice': invoice_data,
                'total': invoice_data['invoice']['total']
            }
        else:  # Si el código de estado no es 200 (OK)
            return {
                # Retorna un diccionario con un mensaje de error indicando que no se pudo obtener la información de la factura
                'success': False,
                'error': 'No se pudo obtener la información de la factura'
            }
    except Exception as e:
        return {
            'success': False,  # Captura cualquier excepción que ocurra durante la ejecución del bloque try
            'error': str(e)  # Retorna un diccionario con un mensaje de error y la descripción de la excepción
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


def process_payment(data, customer_id, token_card, invoice_data):
    print(invoice_data, "hola")
    print("aqui estoy", invoice_data['invoice']['total'])
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
            'description': f'Pago de factura {data["invoice_id"]}',
            # 'description': 'Pago de servicios',
            # 'value': data['value'],
            'value': str(invoice_data['invoice']['total']),
            'tax': '0',
            'tax_base': str(invoice_data['invoice']['total']),
            # 'tax_base': data['value'],
            'currency': 'COP'

        }

        print(f"Payment Info: {json.dumps(payment_info, indent=4)}")  # Imprime los datos de la solicitud

        # aqui es donde se hace el llmado a la funcion que envia el pago al correo
        response = epayco.charge.create(payment_info)  # Realiza la solicitud de pago

        if response.get('status') is True:
            update_invoice_status(data['invoice_id'], response.get('data', {}))

        # response = epayco.charge.create(payment_info)
        return response
    except Exception as e:
        return {'error': str(e)}


def update_invoice_status(invoice_id, payment_data):
    try:
        update_url = f"http://127.0.0.1:3333/invoices/{invoice_id}"
        update_data = {
            "payment_status": "PAID",
            "payment_reference": payment_data.get('ref_payco'),
            "payment_date": payment_data.get('transaction_date'),
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
        required_fields = ['invoice_id', 'card_number', 'exp_year', 'exp_month', 'cvc',
                           'name', 'last_name', 'email', 'doc_number', 'city', 'address',
                           'phone', 'cell_phone']

        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"El campo {field} es requerido"}), 400

        # Obtener detalles de la factura
        invoice_response = get_invoice_details(data)
        if not invoice_response['success']:
            return jsonify({"error": invoice_response['error']}), 400

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
        payment_response = process_payment(data, customer_id, token_card, invoice_response['invoice'])
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