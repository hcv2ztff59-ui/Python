import resend

resend.api_key = "re_Mm6BSpWK_4V8zE692tmzf9cxKRwNDL8sS"

def send_reset_email(email: str, reset_link: str):

    params = {
        "from": "Todo App <onboarding@resend.dev>",
        "to": [email],
        "subject": "Recupero password",
        "html": f"""
        <h2>Recupero password</h2>

        <p>Hai richiesto il reset della password.</p>

        <p>
            <a href="{reset_link}">
                Reimposta Password
            </a>
        </p>

        <p>Il link scadrà tra 1 ora.</p>
        """
    }

    resend.Emails.send(params)