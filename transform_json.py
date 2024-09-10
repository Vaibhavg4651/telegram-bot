import json
from datetime import datetime
import httpx
import json
from typing import Dict, Any
from dotenv import load_dotenv
import os

def transform_json(input_data):
    # Define the mapping between input keys and output columns
    mapping = {
        "Date": "c-sR22rsbBcC",
        "RegistrationNo": "c-W0McKYthDf",
        "ManufacturingYear": "c-UQt5LK15RM",
        "MakeModelVariant": "c-mf9mAarpOA",
        "SeatingCapacity": "c-Qa32_njjLx",
        "FuelType": "c-V9UNwtB77V",
        "CubicCapacity": "c-8vAzvKc8fa",
        "VehicleIDV": "c-loMgDi_JFr",
        "NoClaimBonus": "c-K6xxLrspLz",
        "ExpiryDate": "c-EelO9tA5wk",
        "ClaimConfirmation": "c--02Q3PjGPF",
        "AddOns": "c-hgaUlISQaU",
        "CompanyName": "c-Dh-liwz6_W",
        "LastYearPremium": "c-yQid7hYnPZ",
        "chat_id": "c-60r9Hff-gl",
        "message_id": "c-Dp3zZxHYP1",
        "user_id": "c-loMgDi_JFr",
        "username": "c-hOPAED0bLS"
    }

    # Create the cells list
    cells = [
        {"column": column, "value": input_data.get(key, "N/A")}
        for key, column in mapping.items()
    ]

    # Add additional fields with "Vaibhav" as the value
    additional_columns = [
        "c-md7TDM1BNP", "c-nwjX-Xlu7c", "c-UbW21g2ySx"

    ]
    cells.extend([{"column": col, "value": ""} for col in additional_columns])

    # Create the output structure
    output = {
        "rows": [
            {
                "cells": cells
            }
        ]
    }

    return output



async def send_to_coda(response_Data: Dict[str, Any]):
    CODA_API_URL = os.getenv("CODA_API_URL")
    CODA_API_KEY = os.getenv("CODA_API_KEY")  # Replace with your actual Coda API key

    headers = {
        "Authorization": f"Bearer {CODA_API_KEY}",
        "Content-Type": "application/json"
    }

    # Transform the response_Data into the format expected by Coda
    transformed_data = transform_json(response_Data)

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(CODA_API_URL, json=transformed_data, headers=headers)
            response.raise_for_status()  # Raises an exception for 4xx/5xx status codes

        print("Data successfully sent to Coda:")
        return "Data successfully sent to Coda."

    except httpx.RequestError as e:
        error_message = f"An error occurred while sending the request to Coda: {str(e)}"
        print(error_message)
        return error_message

    except httpx.HTTPStatusError as e:
        error_message = f"Coda API returned an error: {e.response.status_code} {e.response.text}"
        print(error_message)
        return error_message

    except Exception as e:
        error_message = f"An unexpected error occurred: {str(e)}"
        print(error_message)
        return error_message
