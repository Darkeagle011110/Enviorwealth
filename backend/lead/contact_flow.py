from pydantic import BaseModel, EmailStr
from typing import Optional

class ContactSubmission(BaseModel):
    name: str
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    consent_to_contact: bool = False

def process_contact_submission(session_id: str, contact: ContactSubmission):
    """
    Saves the user's contact information and consent to the database.
    Updates the lead score if they were previously gated on contact.
    """
    # In a real system, this would write to the DB.
    # We would associate the contact info with the session_id's lead record.
    return {
        "status": "success",
        "message": "Contact information saved.",
        "session_id": session_id,
        "contact_stored": True
    }
