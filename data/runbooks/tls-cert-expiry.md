# Expired TLS certificate

## Symptoms
TLS handshakes fail with x509 certificate-expired errors. Effectively 100% outage on the endpoint.

## Steps
- Renew the certificate through the normal issuer (cert-manager / ACM / manual CSR).
- Verify the full certificate chain serves correctly from the edge.
- Rotate and redeploy so every terminator picks up the new cert.

## Rollback
Reinstall the previous valid certificate if the renewal is misissued.

## Risk
Medium. Renewal is routine; a bad chain breaks everything the same way.
