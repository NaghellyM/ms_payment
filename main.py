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

