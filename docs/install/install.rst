===================================
Installation and Deployment Options
===================================


Selecting a platform for QATrack+
---------------------------------

Currently there are three "officially" supported ways to deploy QATrack+: 1)
Ubuntu Linux 24.04 LTS with PostgreSQL (recommended; 22.04 LTS is also tested,
and MySQL remains supported for existing installations), 2) Windows Server 2022+
with SQL Server, and 3) Docker on a Linux server.

QATrack+ 4.0 needs Python 3.12, which rules out Ubuntu releases older than
22.04: 20.04 and 18.04 do not package it.

The platform you choose will generally depend on what type of system you or
your clinic has the most expertise in and / or your budget (Microsoft tools can
be expensive!).


Supported browsers
------------------

QATrack+ is used through a browser, so this is part of choosing a platform
rather than a detail of it.

**Supported:** any current version of `Microsoft Edge
<https://www.microsoft.com/edge>`__, `Google Chrome
<https://www.google.com/chrome/>`__ or Chromium, and `Mozilla Firefox
<https://www.mozilla.org/firefox/new/>`__. These release continuously, so
"current" means an up-to-date install rather than a version number. Edge is
already present on every supported Windows release, which makes it the
path of least resistance for a Windows Server deployment.

Firefox and Chrome/Chromium are the two the automated browser tests drive, so
they are the two with ongoing evidence behind them rather than only an
intention.

**Not supported: Internet Explorer.** Microsoft ended support for Internet
Explorer 11 in June 2022 and it cannot be installed on a current version of
Windows. Earlier QATrack+ documentation said that Internet Explorer 11 and
above would work; that is withdrawn. If a site is still reaching QATrack+
through Internet Explorer, Edge is installed beside it on every supported
Windows release and is the replacement.

**Untested rather than unsupported:** Safari, and anything else not named
above. Nothing in QATrack+ deliberately excludes them and no defect has been
reported against them, but no automated or manual testing covers them, so a
site using one is on its own if something looks wrong.

.. toctree::
   :maxdepth: 2
   :caption: Ubuntu Linux

   linux
   linux_upgrade_from_3
   linux_upgrade_from_4_0
   linux_upgrade_from_4_0_1


.. toctree::
   :maxdepth: 2
   :caption: Windows Server

   win
   win_upgrade_from_3
   win_upgrade_from_4_0
   win_upgrade_from_4_0_1


Docker runs QATrack+ and its database in containers on a Linux server. It needs
Docker Engine 23.0 or newer and Docker Compose 2.17 or newer; running it on
Windows, including with Docker Desktop, isn't supported. To get started, see
:doc:`docker`.

.. toctree::
   :maxdepth: 2
   :caption: Docker (Linux)

   docker
   docker_upgrade_from_4_0
   docker_upgrade_from_4_0_1


Configuring your QATrack+ Instance
----------------------------------

After installing QATrack+ you will likely want to customize some of the
settings for QATrack+.  All of the available settings and how to set them is
described here:

.. toctree::
   :maxdepth: 1

   config
   authentication_backends
   backup
