.. _dev_schema:

QATrack+ Database Schema
========================

Below you will find the most recently generated database schema diagram for QATrack+
(v3.1.0). To generate a diagram for the current version (v4.0.0) see the
`Generating the schema diagram`_ section below.

.. figure:: images/qatrack_schema_3.1.0.svg
   :alt: QATrack+ v3.1.0 schema

   The QATrack+ v3.1.0 schema (click to view full size or right click and view
   in new tab to view full size)


Generating the schema diagram
-----------------------------


Ubuntu
~~~~~~

On Ubuntu (tested on 22.04) you need to install a few system dependencies before
generating the schema diagram:

.. code-block:: sh

    sudo apt install python3-dev graphviz libgraphviz-dev pkg-config

Then install the Python dependency into the project environment (requires the
``dev`` dependency group):

.. code-block:: sh

    uv sync --group dev

and then you can generate your schema with:

.. code-block:: sh

    make schema

which will output the schema to docs/developer/images/qatrack_schema_$(VERSION).svg


Windows
~~~~~~~

It is also possible to generate a schema diagram on Windows using Sql Server
Management Studio. See
https://dataedo.com/kb/tools/ssms/create-database-diagram for instructions on
making a diagram with SSMS.


Schema for Older Versions
=========================

Older schema diagrams can be found in the ``docs/developer/images/`` directory
of the repository, or by browsing the project history on GitHub:
`QATrack+ on GitHub <https://github.com/qatrackplus/qatrackplus>`__.
