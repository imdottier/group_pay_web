import base64
import logging
import uuid
from fastapi import APIRouter, File, UploadFile, HTTPException, Depends, Request
import google.generativeai as genai
from pydantic import BaseModel, Field
from typing import List, Optional

from backend.config import settings
from backend.dependencies import get_current_user
import backend.models as models
from backend.services.storage_service import upload_file_to_gcs

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/receipt-parser",
    tags=["Receipt Parser"],
    dependencies=[Depends(get_current_user)]
)

# The Generative AI client is now configured globally in main.py on startup

# --- Pydantic Models for AI Response ---

class ParsedItem(BaseModel):
    name: str = Field(description="The name of the item purchased.")
    quantity: int = Field(description="The quantity of the item purchased.")
    unit_price: float = Field(description="The price of a single unit of the item.")

class ParsedReceipt(BaseModel):
    store_name: Optional[str] = Field(description="The name of the store or vendor.", default=None)
    total_amount: float = Field(description="The final total amount of the bill.")
    items: List[ParsedItem] = Field(description="A list of all items on the receipt.")
    image_url: Optional[str] = Field(description="URL to view the uploaded receipt image.", default=None)


# --- The Prompt for the AI Model ---

generation_config = {
    "temperature": 0.2,
    "top_p": 1,
    "top_k": 32,
    "max_output_tokens": 4096,
}

# The prompt is a crucial part of getting good results.
# We instruct the model to act as a JSON API.
prompt = """
You are an intelligent receipt processing assistant. Your task is to analyze the user-provided receipt image and extract structured data from it.

The user will provide an image of a receipt.

Analyze the image and respond with ONLY a valid JSON object that adheres to the following Pydantic model structure:

```json
{
  "store_name": "string or null",
  "total_amount": "float",
  "items": [
    {
      "name": "string",
      "quantity": "integer",
      "unit_price": "float"
    }
  ]
}
```

**Instructions and Rules:**
1.  **JSON Only**: Your entire response must be a single, valid JSON object. Do not include any text before or after the JSON object, such as "Here is the JSON:" or markdown code fences.
2.  **`total_amount`**: This is a mandatory field. Find the final, total price of the bill, including any taxes or tips if specified. Total price is FINAL and ABSOLUTE.
DO NOT CHANGE THE TOTAL AMOUNT IN ANY CASE.
If for any reason total_amount does not match the sum of the unit prices of all items, please calculate the unit price so that they match.
3.  **`items`**: This is a mandatory field. Extract every line item from the receipt. If you cannot find any items, return an empty list `[]`.
4.  **`name`**: For each item, extract its name.
5.  **`quantity`**: Determine the quantity of each item. If not explicitly mentioned, assume the quantity is 1.
6.  **`unit_price`**: Extract the price for a single unit of the item. If the price listed is for multiple items, calculate the per-unit price.
The currency of the image will always be VND, so it's safe to assume that 50k, 50.000, or even 50,000 to be 50 thousand VND unless there's a reason not to.
The current database does not allow VAT or any type of discount, so please calculate the unit price after applying discounts and taxes.
If the discount is based on the total amount, please calculate the unit price based on the ratio between the total amount and the discounted amount.
Round the unit price to the 1000 VND, percentage errors can be tolerated as long as the total amount calculated from all items is correct.
If only one value of unit_price and calculated_price (= unit_price * quantity) is written, decide based on the context (Đơn giá/Tổng giá/...)
If the context is not clear, assume it's unit_price if it appears before quantity and calculated_price vice versa.
7.  **`store_name`**: If you can identify the name of the store or vendor, include it. Otherwise, you can omit the field or set it to null.
8.  **Accuracy**: Be as accurate as possible with total_amount and quantity. Unit_price can be adjusted in case of discount and unmatched value (noted in 9 and example)
9. **IMPORTANT**: Always make sure that the total calculated price from unit prices and quantity match with total_amount.

**Example:**
Unit Price - Quantity - Total:
50k        - 1        - 50k
60k        - 2        - 120k

Total Amount: 200k

**Expected result**:
Unit Price - Quantity
80k        - 1
60k        - 2

Total Amount: 200k

**As total_amount accuracy is absolute, the unit price are adjusted, though this shouldn't happen frequently**

**Example:**
Unit Price - Quantity - Total:
50k        - 2        - 100k
60k        - 2        - 120k

Total Amount :220k
Discount     :20k
Final Amount :200k

**Expected result**:
Unit Price - Quantity
45k        - 2
55k        - 2

Total Amount: 200k

**Based on the ratio between discount and total amount, recalculate unit price and round them to the nearest 1000 VND.
Again total amount is absolute.**
"""

@router.post("/parse-receipt", response_model=ParsedReceipt)
async def parse_receipt_image(
    request: Request,
    file: UploadFile = File(...),
    current_user: models.User = Depends(get_current_user)):
    """
    Receives a receipt image, sends it to Google's Generative AI for parsing,
    and returns the structured data.
    """
    user_id = current_user.user_id
    logger.info(f"User {user_id} initiated receipt parsing for file: {file.filename} ({file.content_type})")

    # The AI client is configured on startup. If it's not available, the feature is disabled.
    if not request.app.state.google_ai_configured:
        logger.error("Receipt parsing endpoint called, but Generative AI client is not configured.")
        raise HTTPException(
            status_code=501, # 501 Not Implemented
            detail="The receipt parsing feature is not configured on the server."
        )

    if not file.content_type or not file.content_type.startswith("image/"):
        logger.warning(f"User {user_id} uploaded an invalid file type: {file.content_type}")
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload an image.")

    image_url = None
    try:
        # Read the file content once to be used by GCS and AI
        contents = await file.read()

        # Rewind the file pointer after reading
        await file.seek(0)

        # --- File Upload to GCS ---
        try:
            image_url = await upload_file_to_gcs(file, destination_path="receipts")
            logger.info(f"Successfully uploaded receipt for user {user_id} to GCS. URL: {image_url}")
        except HTTPException as e:
            # Log the specific GCS upload error and re-raise
            logger.error(f"GCS upload failed for user {user_id}: {e.detail}")
            raise e # Re-raise the exception from the service

        # --- AI Processing ---
        # Prepare the image for the model using the contents read earlier
        image_blob = {
            'mime_type': file.content_type,
            'data': base64.b64encode(contents).decode('utf-8')
        }

        # Initialize the model
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash-latest",
            generation_config=generation_config
        )
        logger.info(f"Generative AI model 'gemini-1.5-flash-latest' initialized for user {user_id}.")

        # Send the prompt and the image to the model
        logger.info(f"Sending request to Generative AI for user {user_id}...")
        response = await model.generate_content_async([prompt, image_blob])
        
        raw_text = response.text
        logger.info(f"Received response from Generative AI for user {user_id}. Raw text length: {len(raw_text)}")
        logger.debug(f"Raw AI response for user {user_id}:\n---START---\n{raw_text}\n---END---")


        # Extract the JSON from the response
        # The response may contain markdown ```json ... ```, so we clean it up.
        cleaned_json_str = raw_text.strip().replace("```json", "").replace("```", "").strip()
        logger.info(f"Cleaned JSON string for user {user_id}. Length: {len(cleaned_json_str)}")
        logger.debug(f"Cleaned JSON for user {user_id}:\n---START---\n{cleaned_json_str}\n---END---")
        
        # Parse the JSON string into our Pydantic model
        parsed_data = ParsedReceipt.parse_raw(cleaned_json_str)
        # Add the image URL to the response
        parsed_data.image_url = image_url
        logger.info(f"Successfully parsed AI response into Pydantic model for user {user_id}.")
        return parsed_data

    except Exception as e:
        # Check if 'response' exists to avoid another error
        raw_response_text = "N/A"
        if 'response' in locals() and hasattr(response, 'text'):
            raw_response_text = response.text

        logger.exception(
            f"An unexpected error occurred during receipt parsing for user {user_id}. "
            f"Error: {e}. Raw AI Output: '{raw_response_text}'"
        )
        
        raise HTTPException(
            status_code=500,
            detail=f"Failed to parse receipt. The AI model may have returned an invalid format or an error occurred."
        ) 