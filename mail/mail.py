import resend

resend.api_key = "re_Mm6BSpWK_4V8zE692tmzf9cxKRwNDL8sS"

def send_email(email: str, reset_link: str, obj:str , body: str):

    params = {
        "from": "Pladdy <support@pladdy.it>",
        "to": [email],
        "subject": obj,
        "html": body 
    }

    resend.Emails.send(params)
    
    
    
    '''
    
    f"""
        <h2>Recupero password</h2>

        <p>Hai richiesto il reset della password.</p>

        <p>
            <a href="{reset_link}">
                Reimposta Password
            </a>
        </p>

        <p>Il link scadrà tra 1 ora.</p>
    '''