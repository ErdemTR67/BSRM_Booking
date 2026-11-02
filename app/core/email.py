import smtplib
from datetime import datetime
from email.message import EmailMessage
from html import escape

from app.core.config import Settings, get_settings


class InvitationEmailSender:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def send(self, *, recipient: str, tenant_name: str, invitation_url: str) -> None:
        if self.settings.email_delivery_mode == "console":
            return

        message = self.build_message(
            recipient=recipient,
            tenant_name=tenant_name,
            invitation_url=invitation_url,
        )

        with smtplib.SMTP(
            self.settings.smtp_host,
            self.settings.smtp_port,
            timeout=15,
        ) as smtp:
            if self.settings.smtp_use_tls:
                smtp.starttls()
            if self.settings.smtp_username:
                password = (
                    self.settings.smtp_password.get_secret_value()
                    if self.settings.smtp_password is not None
                    else ""
                )
                smtp.login(self.settings.smtp_username, password)
            smtp.send_message(message)

    def build_message(
        self,
        *,
        recipient: str,
        tenant_name: str,
        invitation_url: str,
    ) -> EmailMessage:
        safe_tenant_header = " ".join(tenant_name.split())
        safe_tenant_html = escape(safe_tenant_header)
        safe_invitation_url = escape(invitation_url, quote=True)
        expiration_hours = self.settings.invitation_expire_hours

        message = EmailMessage()
        message["Subject"] = f"Invitation à rejoindre {safe_tenant_header}"
        message["From"] = self.settings.smtp_from_email
        message["To"] = recipient
        message["Auto-Submitted"] = "auto-generated"
        message.set_content(
            "Invitation à rejoindre BSRM Booking\n\n"
            f"Vous êtes invité(e) à rejoindre {safe_tenant_header} sur BSRM Booking.\n\n"
            "Configurez votre compte à l'aide de ce lien sécurisé :\n"
            f"{invitation_url}\n\n"
            f"Ce lien est personnel, à usage unique et expire dans {expiration_hours} heures.\n"
            "Si vous n'attendiez pas cette invitation, vous pouvez ignorer cet e-mail."
        )
        message.add_alternative(
            self._html_content(
                tenant_name=safe_tenant_html,
                invitation_url=safe_invitation_url,
                expiration_hours=expiration_hours,
            ),
            subtype="html",
        )
        return message

    @staticmethod
    def _html_content(
        *,
        tenant_name: str,
        invitation_url: str,
        expiration_hours: int,
    ) -> str:
        return f"""\
<!doctype html>
<html lang="fr">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="color-scheme" content="light only">
    <title>Invitation BSRM Booking</title>
    <style>
      @media only screen and (max-width: 640px) {{
        .email-shell {{ width: 100% !important; }}
        .content-cell {{ padding-left: 24px !important; padding-right: 24px !important; }}
        .brand-title {{ font-size: 24px !important; }}
        .page-title {{ font-size: 38px !important; line-height: 42px !important; }}
      }}
    </style>
  </head>
  <body style="margin:0; padding:0; background:#FFFFFF; color:#000000;">
    <div style="display:none; max-height:0; overflow:hidden; opacity:0; color:#FFFFFF;">
      {tenant_name} vous invite à rejoindre son espace BSRM Booking.
    </div>
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="width:100%; background:#FFFFFF;">
      <tr>
        <td align="center" style="padding:32px 12px;">
          <table role="presentation" width="640" cellspacing="0" cellpadding="0" border="0" class="email-shell" style="width:640px; max-width:640px; border:1px solid #000000; border-collapse:collapse;">
            <tr>
              <td style="background:#000000; padding:22px 32px; border-bottom:4px solid #9470BA;">
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                  <tr>
                    <td class="brand-title" style="font-family:'Big Caslon','Book Antiqua',Georgia,serif; font-size:28px; line-height:32px; color:#FFFFFF;">
                      BSRM Booking
                    </td>
                    <td align="right" style="font-family:Arial,sans-serif; font-size:11px; line-height:16px; letter-spacing:1.8px; text-transform:uppercase; color:#B1A8B9;">
                      Invitation
                    </td>
                  </tr>
                </table>
              </td>
            </tr>
            <tr>
              <td class="content-cell" style="padding:48px 48px 28px;">
                <table role="presentation" cellspacing="0" cellpadding="0" border="0" style="margin-bottom:22px;">
                  <tr>
                    <td width="42" style="width:42px; border-top:1px solid #8074C8; font-size:1px; line-height:1px;">&nbsp;</td>
                    <td width="8" style="width:8px;">&nbsp;</td>
                    <td width="7" height="7" style="width:7px; height:7px; background:#9470BA; border-radius:50%; font-size:1px; line-height:1px;">&nbsp;</td>
                  </tr>
                </table>
                <div style="font-family:Arial,sans-serif; font-size:11px; line-height:16px; letter-spacing:1.6px; text-transform:uppercase; color:#4B4452; margin-bottom:14px;">
                  Accès à votre espace
                </div>
                <h1 class="page-title" style="margin:0; font-family:'Big Caslon','Book Antiqua',Georgia,serif; font-weight:400; font-size:48px; line-height:52px; color:#000000;">
                  Rejoignez<br>{tenant_name}
                </h1>
              </td>
            </tr>
            <tr>
              <td class="content-cell" style="padding:0 48px 34px;">
                <p style="margin:0 0 24px; font-family:Arial,sans-serif; font-size:16px; line-height:25px; color:#4B4452;">
                  Vous avez été invité(e) à rejoindre l’espace de gestion de <strong style="color:#000000;">{tenant_name}</strong>. Configurez votre compte pour accéder aux établissements, équipes et rendez-vous.
                </p>
                <table role="presentation" cellspacing="0" cellpadding="0" border="0">
                  <tr>
                    <td style="background:#000000; border-left:5px solid #8074C8;">
                      <a href="{invitation_url}" style="display:inline-block; padding:15px 24px; font-family:Arial,sans-serif; font-size:14px; line-height:18px; font-weight:bold; letter-spacing:0.3px; color:#FFFFFF; text-decoration:none;">
                        Configurer mon compte&nbsp;&nbsp;→
                      </a>
                    </td>
                  </tr>
                </table>
              </td>
            </tr>
            <tr>
              <td class="content-cell" style="padding:0 48px 36px;">
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="border-top:1px solid #B1A8B9; border-bottom:1px solid #B1A8B9;">
                  <tr>
                    <td style="padding:18px 0; font-family:Arial,sans-serif; font-size:12px; line-height:19px; color:#4B4452;">
                      <strong style="color:#000000;">Lien sécurisé.</strong> Cette invitation est personnelle, utilisable une seule fois et expire dans {expiration_hours} heures.
                    </td>
                  </tr>
                </table>
              </td>
            </tr>
            <tr>
              <td class="content-cell" style="padding:0 48px 42px;">
                <p style="margin:0 0 8px; font-family:Arial,sans-serif; font-size:12px; line-height:18px; color:#4B4452;">
                  Si le bouton ne fonctionne pas, copiez ce lien dans votre navigateur :
                </p>
                <p style="margin:0; font-family:Arial,sans-serif; font-size:11px; line-height:17px; word-break:break-all; color:#8074C8;">
                  {invitation_url}
                </p>
              </td>
            </tr>
            <tr>
              <td style="background:#4B4452; padding:18px 32px;">
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                  <tr>
                    <td style="font-family:Arial,sans-serif; font-size:11px; line-height:17px; color:#FFFFFF;">
                      BSRM Booking · Une interface Bosphoreum
                    </td>
                    <td align="right" style="font-family:Arial,sans-serif; font-size:11px; line-height:17px; color:#B1A8B9;">
                      Si vous n’attendiez pas cet e-mail, ignorez-le.
                    </td>
                  </tr>
                </table>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>
"""


class AppointmentConfirmationEmailSender:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def send_confirmation(
        self,
        *,
        recipient: str,
        customer_name: str,
        reference: str,
        tenant_name: str,
        location_name: str,
        employee_name: str,
        starts_at: datetime,
        ends_at: datetime,
        service_name: str,
        price_cents: int | None,
        currency: str,
    ) -> None:
        if self.settings.email_delivery_mode == "console":
            return
        message = self.build_confirmation_message(
            recipient=recipient,
            customer_name=customer_name,
            reference=reference,
            tenant_name=tenant_name,
            location_name=location_name,
            employee_name=employee_name,
            starts_at=starts_at,
            ends_at=ends_at,
            service_name=service_name,
            price_cents=price_cents,
            currency=currency,
        )
        with smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port, timeout=15) as smtp:
            if self.settings.smtp_use_tls:
                smtp.starttls()
            if self.settings.smtp_username:
                password = (
                    self.settings.smtp_password.get_secret_value()
                    if self.settings.smtp_password is not None
                    else ""
                )
                smtp.login(self.settings.smtp_username, password)
            smtp.send_message(message)

    def build_confirmation_message(
        self,
        *,
        recipient: str,
        customer_name: str,
        reference: str,
        tenant_name: str,
        location_name: str,
        employee_name: str,
        starts_at: datetime,
        ends_at: datetime,
        service_name: str,
        price_cents: int | None,
        currency: str,
    ) -> EmailMessage:
        safe_customer = escape(customer_name)
        safe_reference = escape(reference)
        safe_tenant = escape(tenant_name)
        safe_location = escape(location_name)
        safe_employee = escape(employee_name)
        safe_service = escape(service_name)
        price = (
            f"{price_cents / 100:.2f} {currency}".replace(".", ",")
            if price_cents is not None
            else "Prix communiqué sur place"
        )
        message = EmailMessage()
        message["Subject"] = f"Confirmation de réservation : {reference}"
        message["From"] = self.settings.smtp_from_email
        message["To"] = recipient
        message["Auto-Submitted"] = "auto-generated"
        message.set_content(
            f"Bonjour {customer_name},\n\n"
            f"Votre réservation chez {tenant_name} est enregistrée.\n"
            f"Prestation : {service_name}\n"
            f"Établissement : {location_name}\n"
            f"Professionnel : {employee_name}\n"
            f"Début : {starts_at.isoformat()}\n"
            f"Fin : {ends_at.isoformat()}\n"
            f"Prix : {price}\n"
            f"Référence : {reference}\n"
        )
        message.add_alternative(
            f"""<!doctype html>
<html lang="fr"><body style="margin:0;background:#FFFFFF;color:#000000">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0"><tr><td align="center" style="padding:32px 12px">
<table role="presentation" width="640" cellspacing="0" cellpadding="0" style="width:640px;max-width:100%;border:1px solid #000000;border-collapse:collapse">
<tr><td style="background:#000000;color:#FFFFFF;padding:22px 32px;border-bottom:4px solid #9470BA;font-family:'Big Caslon','Book Antiqua',Georgia,serif;font-size:28px">BSRM Booking</td></tr>
<tr><td style="padding:44px 44px 24px"><div style="font:11px Arial,sans-serif;letter-spacing:1.5px;text-transform:uppercase;color:#4B4452">Réservation confirmée</div>
<h1 style="font-family:'Big Caslon','Book Antiqua',Georgia,serif;font-weight:400;font-size:42px;line-height:46px;margin:12px 0 18px">À bientôt chez {safe_tenant}</h1>
<p style="font:16px/25px Arial,sans-serif;color:#4B4452">Bonjour {safe_customer}, votre rendez-vous est bien enregistré.</p></td></tr>
<tr><td style="padding:0 44px 36px"><table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="border-top:1px solid #B1A8B9">
<tr><td style="padding:12px 0;font:13px Arial,sans-serif;color:#4B4452">Prestation</td><td align="right" style="font:14px Arial,sans-serif">{safe_service}</td></tr>
<tr><td style="padding:12px 0;border-top:1px solid #B1A8B9;font:13px Arial,sans-serif;color:#4B4452">Établissement</td><td align="right" style="border-top:1px solid #B1A8B9;font:14px Arial,sans-serif">{safe_location}</td></tr>
<tr><td style="padding:12px 0;border-top:1px solid #B1A8B9;font:13px Arial,sans-serif;color:#4B4452">Professionnel</td><td align="right" style="border-top:1px solid #B1A8B9;font:14px Arial,sans-serif">{safe_employee}</td></tr>
<tr><td style="padding:12px 0;border-top:1px solid #B1A8B9;font:13px Arial,sans-serif;color:#4B4452">Horaire</td><td align="right" style="border-top:1px solid #B1A8B9;font:14px Arial,sans-serif">Du {starts_at.isoformat()} au {ends_at.isoformat()}</td></tr>
<tr><td style="padding:12px 0;border-top:1px solid #B1A8B9;font:13px Arial,sans-serif;color:#4B4452">Prix</td><td align="right" style="border-top:1px solid #B1A8B9;font:14px Arial,sans-serif">{escape(price)}</td></tr>
</table></td></tr>
<tr><td style="background:#4B4452;color:#FFFFFF;padding:18px 32px;font:12px Arial,sans-serif">Référence&nbsp;: <strong>{safe_reference}</strong></td></tr>
</table></td></tr></table></body></html>""",
            subtype="html",
        )
        return message
