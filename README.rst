OMERO.tagsearch
================
OMERO.tagsearch is a plugin for `OMERO.web <https://github.com/ome/omero-web>`_ that enables searching of data using tags, with the search continuously refined as available search terms are entered and further term suggestions based on the entered terms are offered. 
This can be used in a way that is similar to navigating a file system hierarchy.

This was formerly part of `OMERO.webtagging <https://github.com/German-BioImaging/webtagging>`_, the umbrella name for tools developed to enhance use of text annotations (tags) in OMERO.

Requirements
============

As Python 2 has now reached end-of-life, OMERO 5.6 now
requires Python 3. With release 3.1.0 of tagsearch, the following are now required. To use tagsearch on older OMERO systems (running Python 2),
please use versions older than 3.1.0.

* Python 3.5 or later
* omero-web 5.6 or later
* django 1.11 or later

User Documentation
==================

http://help.openmicroscopy.org/web-tagging.html


Installation
============

The recommended way to install tagsearch is using `pip`, but it is also possible
to install it manually as described `here <https://www.openmicroscopy.org/site/support/omero5/developers/Web/CreateApp.html#add-your-app-location-to-your-pythonpath>`_.

::

  # In the python environment of OMERO.web (virtualenv or global)
  pip install omero-tagsearch

  # Add tagsearch to webclient
  omero config append omero.web.apps '"omero_tagsearch"'

  # Add a top-link to tagsearch designer
  omero config append omero.web.ui.top_links '["Tag Search", "tagsearch"]'

Upgrade from omero-webtagging-tagsearch to omero-tagsearch
==========================================================

Since 3.2.2, the package was renamed to `omero-tagsearch`. This is a breaking change for OMERO.web, as the old package must be removed from the OMERO.web config and replaced by the new package.

You can perform the upgrade as follow:

::

  # stop omero web
  # Install the new package and uninstall the old one
  pip uninstall omero-webtagging-tagsearch  
  pip install omero-tagsearch

  # Then open the OMERO.web configuration editor
  omero config edit
  # Update the configuration called 'omero.web.apps'
  # In 'omero.web.apps': 'omero_webtagging_tagsearch' -> 'omero_tagsearch'
  # start omero web

Note that installing the latest `omero-webtagging-autotag` is not functional but has a dependency on `omero-autotag`. 
Thus, if you wish to use the old version `omero-webtagging-tagsearch`, make sure to specify the latest working version:

::

  # ONLY IF YOU WANT TO USE AN OLDER VERSION OF THE PLUGIN
  # stop omero web
  pip install omero-webtagging-tagsearch==3.2.0
  # And set the configuration accordingly
  # start omero web


Documentation
=============

Available on the `OMERO website <http://help.openmicroscopy.org/web-tagging.html>`_.


Development
===========

Pure javascript so does not require a node build step.

To install using pip in development mode (in appropriate virtualenv)

::
  # In the top-level tagsearch directory containing setup.py
  pip install -e .
  cd $OMERO_PREFIX

OMERO development server can then be started in the usual way. Remember to
configure the tagsearch settings the same as above.

Project Maintenance
===================

I (Douglas) am no longer actively developing
OMERO.webtagging. I am thrilled to hand over
maintainence and development to
`German Bioimaging <https://gerbi-gmb.de/i3dbio/i3dbio-about/>`_.

Acknowledgements
================

OMERO.webtagging was created by Douglas P. W. Russell
(dpwrussell@gmail.com) while at Oxford University and
Harvard Medical School, then later extended by DPWR
Consulting Ltd.

These plugins were developed originally with the
support of [Micron Advanced Bioimaging Unit](https://micronoxford.com/)
funded by the Wellcome Trust Strategic Award 091911,
and [Open Microscopy](https://www.openmicroscopy.org/).

Continued development was supported by [The Laboratory
of Systems Pharmacology, Harvard Medical School](https://hits.harvard.edu/the-program/laboratory-of-systems-pharmacology/research-program/) and
[Research Computing, Harvard Medical School](https://it.hms.harvard.edu/our-services/research-computing).

Continued development was sponsored by
[Micron Advanced Bioimaging Unit](https://micronoxford.com/)
funded by the Wellcome Trust Strategic Award 107457.
