:orphan:

.. important:: Security Considerations

   QATrack+ is designed and tested for deployment on a trusted intranet -
   typically a hospital or clinic's internal network - not for direct
   exposure to the public internet. It has not been security-audited for
   internet-facing deployment, and doing so isn't recommended without
   additional protections (a VPN, reverse-proxy authentication, etc.) that
   are outside the scope of these docs.

   Regardless of your network's trust level, **change the example database
   password shown above** (``qatrackpass``) to something unique to your
   organization before going into production. It's the literal example
   used throughout this open-source project's documentation, so treat it
   as public knowledge, not a secret.

   Beyond that, firewall rules, network segmentation, and what's
   appropriate for your specific environment are properly a decision for
   your organization's own IT/security policies - these docs can't
   prescribe that for you.
