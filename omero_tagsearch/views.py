from __future__ import absolute_import
from builtins import str
import json
import logging
from collections import defaultdict
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse
from django.template.loader import render_to_string
from omeroweb.webclient.decorators import render_response, login_required
from omero.sys import Parameters
from omero.rtypes import rlong, rlist
from omeroweb.webclient.views import switch_active_group
from omeroweb.webclient.forms import GlobalSearchForm, ContainerForm
from .forms import TagSearchForm

logger = logging.getLogger(__name__)


@login_required()
@render_response()
def index(request, conn=None, **kwargs):
    request.session.modified = True

    # TODO Hardcode menu as search until I figure out what to do with menu
    menu = "search"
    template = "omero_tagsearch/tagnav.html"

    # tree support
    init = {"initially_open": None, "initially_select": []}
    selected = None
    initially_open_owner = None

    # E.g. backwards compatible support for
    # path=project=51|dataset=502|image=607 (select the image)
    path = request.GET.get("path", "")
    i = path.split("|")[-1]
    if i.split("=")[0] in ("project", "dataset", "image", "screen",
                           "plate", "tag", "acquisition", "run", "well"):
        init["initially_select"].append(str(i).replace("=", "-"))

    # Now we support show=image-607|image-123  (multi-objects selected)
    show = request.GET.get("show", "")
    for i in show.split("|"):
        if i.split("-")[0] in (
            "project",
            "dataset",
            "image",
            "screen",
            "plate",
            "tag",
            "acquisition",
            "run",
            "well",
        ):
            # alternatives for 'acquisition'
            i = i.replace("run", "acquisition")
            init["initially_select"].append(str(i))

    if len(init["initially_select"]) > 0:
        # tree hierarchy open to first selected object
        init["initially_open"] = [init["initially_select"][0]]
        first_obj, first_id = init["initially_open"][0].split("-", 1)

        # if we're showing a tag, make sure we're on the tags page...
        if first_obj == "tag" and menu != "usertags":
            return HttpResponseRedirect(
                reverse(viewname="load_template", args=["usertags"])
                + "?show="
                + init["initially_select"][0]
            )

        try:
            # set context to 'cross-group'
            conn.SERVICE_OPTS.setOmeroGroup("-1")
            if first_obj == "tag":
                selected = conn.getObject("TagAnnotation", int(first_id))
            else:
                selected = conn.getObject(first_obj, int(first_id))
                initially_open_owner = selected.details.owner.id.val
                # Wells aren't in the tree, so we need parent...
                if first_obj == "well":
                    ws = selected.getWellSample()
                    parent_node = ws.getPlateAcquisition()
                    ptype = "acquisition"
                    # No Acquisition for this well, use Plate instead
                    if parent_node is None:
                        parent_node = selected.getParent()
                        ptype = "plate"
                    selected = parent_node
                    init["initially_open"] = [f"{ptype}-{parent_node.getId()}"]
                    init["initially_select"] = init["initially_open"][:]
        except Exception:
            # invalid id
            pass
        if first_obj not in ("project", "screen"):
            # need to see if first item has parents
            if selected is not None:
                for p in selected.getAncestry():
                    # parents of tags must be tags (no OMERO_CLASS)
                    if first_obj == "tag":
                        init["initially_open"].insert(0, "tag-%s" % p.getId())
                    else:
                        init["initially_open"].insert(
                            0, "%s-%s" % (p.OMERO_CLASS.lower(), p.getId())
                        )
                        initially_open_owner = p.details.owner.id.val
                if init["initially_open"][0].split("-")[0] == "image":
                    init["initially_open"].insert(0, "orphaned-0")

    # need to be sure that tree will be correct omero.group
    if selected is not None:
        switch_active_group(request, selected.details.group.id.val)

    # search support
    global_search_form = GlobalSearchForm(data=request.GET.copy())
    if menu == "search":
        if global_search_form.is_valid():
            init["query"] = global_search_form.cleaned_data["search_query"]

    # get url without request string - used to refresh page after switch
    # user/group etc
    url = reverse(viewname="tagsearch")

    # validate experimenter is in the active group
    active_group = (request.session.get("active_group")
                    or conn.getEventContext().groupId)
    # prepare members of group...
    s = conn.groupSummary(active_group)
    leaders = s["leaders"]
    members = s["colleagues"]
    userIds = [u.id for u in leaders]
    userIds.extend([u.id for u in members])
    users = []
    if len(leaders) > 0:
        users.append(("Owners", leaders))
    if len(members) > 0:
        users.append(("Members", members))
    users = tuple(users)

    # check any change in experimenter...
    user_id = request.GET.get("experimenter")
    if initially_open_owner is not None:
        # if we're not already showing 'All Members'...
        if request.session.get("user_id", None) != -1:
            user_id = initially_open_owner
    try:
        user_id = int(user_id)
    except Exception:
        user_id = None

    # Check is user_id is in a current group
    if (
        user_id not in (set([x.id for x in leaders])
                        | set([x.id for x in members]))
        and user_id != -1
    ):
        # All users in group is allowed
        user_id = None

    if user_id is None:
        # ... or check that current user is valid in active group
        user_id = request.session.get("user_id", None)
        if user_id is None or int(user_id) not in userIds:
            if user_id != -1:  # All users in group is allowed
                user_id = conn.getEventContext().userId

    request.session["user_id"] = user_id

    if conn.isAdmin():  # Admin can see all groups
        myGroups = [
            g
            for g in conn.getObjects("ExperimenterGroup")
            if g.getName() not in ("user", "guest")
        ]
    else:
        myGroups = list(conn.getGroupsMemberOf())
    myGroups.sort(key=lambda x: x.getName().lower())
    new_container_form = ContainerForm()

    fullname_d = {exp.getId(): exp for exp in leaders + members}
    user_name = ""
    if user_id != -1:
        user_name = fullname_d[user_id].getFullName()

    # Create and set the form

    qs = conn.getQueryService()
    service_opts = conn.SERVICE_OPTS.copy()
    service_opts.setOmeroGroup(active_group)

    def get_namespaces():

        params = Parameters()
        hql = (
                """
                SELECT DISTINCT ann.ns
                FROM Annotation ann
            """
        )

        if user_id != -1:
            hql += " WHERE ann.details.owner.id = (:uid)"
            params.map = {"uid": rlong(user_id)}

        return [
            result[0].val for result in qs.projection(hql, params, service_opts) if len(result) > 0
        ]

    def get_tags(obj, tagset_d):
        # Get tags
        # It is not sufficient to simply get the objects as there may be tags
        # which are not applied which don't really make sense to display
        # tags = list(self.conn.getObjects("TagAnnotation"))

        params = Parameters()
        hql = (
            """
            SELECT DISTINCT ann.id, ann.textValue
            FROM %sAnnotationLink link
            JOIN link.child ann
            WHERE ann.class IS TagAnnotation
        """
            % obj
        )

        if user_id != -1:
            hql += " AND ann.details.owner.id = (:uid)"
            params.map = {"uid": rlong(user_id)}

        return [
            (result[0].val, result[1].val, tagset_d[result[0].val])
            for result in qs.projection(hql, params, service_opts)
        ]

    def get_key_values(obj):
        # Get keys

        params = Parameters()
        hql = (
            """
            SELECT DISTINCT ann.id, map.name, map.value
            FROM %sAnnotationLink link
            JOIN link.child ann
            JOIN ann.mapValue map
            WHERE ann.class IS MapAnnotation
        """
            % obj
        )

        if user_id != -1:
            hql += " AND ann.details.owner.id = (:uid)"
            params.map = {"uid": rlong(user_id)}

        return [
            (result[0].val, result[1].val, result[2].val) for result in qs.projection(hql, params, service_opts)
        ]

    def get_tagsets():
        # Get tagsets for tag_ids
        # Do not filter tagsets on user, as it's meant to be
        # information added to tags

        params = Parameters()
        hql = (
            """
            SELECT DISTINCT link.child.id, tagset.textValue
            FROM Annotation tagset
            JOIN tagset.annotationLinks link
            WHERE tagset.class IS TagAnnotation
            """
        )

        return {
            result[0].val: f" [{result[1].val}]"
            for result in qs.projection(hql, params, service_opts)
        }

    tagset_d = defaultdict(str)
    tagset_d.update(get_tagsets())

    # List of tuples (id, value)
    tags = set(get_tags("Image", tagset_d))
    tags.update(get_tags("Dataset", tagset_d))
    tags.update(get_tags("Project", tagset_d))
    tags.update(get_tags("Plate", tagset_d))
    tags.update(get_tags("PlateAcquisition", tagset_d))
    tags.update(get_tags("Screen", tagset_d))
    tags.update(get_tags("Well", tagset_d))

    # List of tuples (name, value)
    kvps = set(get_key_values("Image"))
    kvps.update(get_key_values("Dataset"))
    kvps.update(get_key_values("Project"))
    kvps.update(get_key_values("Plate"))
    kvps.update(get_key_values("PlateAcquisition"))
    kvps.update(get_key_values("Screen"))
    kvps.update(get_key_values("Well"))

    namespaces = get_namespaces()

    # Convert back to an ordered list and sort
    tags = list(tags)
    tags.sort(key=lambda x: (x[2].lower(), x[1].lower()))
    tags = list(map(lambda t: (t[0], t[1] + t[2]), tags))

    # Convert back to an ordered list and sort
    kvps = list(kvps)
    kvps.sort(key=lambda x: x[1].lower())
    keys = sorted(list(set(map(lambda t: (t[1], t[1]), kvps))))
    keys.insert(0, ("_Choose Key_", "_Choose Key_"))
    values = sorted(list(set(map(lambda t: (t[2], t[2]), kvps))))
    values.insert(0, ("_Choose Value_", "_Choose Value_"))

    namespaces = [(x, x) for x in namespaces]

    tag_form = TagSearchForm(tags, keys, values, namespaces, conn, use_required_attribute=False)

    context = {
        "init": init,
        "myGroups": myGroups,
        "new_container_form": new_container_form,
        "global_search_form": global_search_form,
    }
    context["groups"] = myGroups
    context["active_group"] = conn.getObject("ExperimenterGroup",
                                             int(active_group))
    for g in context["groups"]:
        g.groupSummary()  # load leaders / members
    context["active_user"] = conn.getObject("Experimenter", int(user_id))

    context["isLeader"] = conn.isLeader()
    context["current_url"] = url
    context["template"] = template
    context["tagnav_form"] = tag_form
    context["user_name"] = user_name

    return context


@login_required(setGroupContext=True)
# TODO Figure out what happened to render_response as it wasn't working on
# production
# @render_response()
def tag_image_search(request, conn=None, **kwargs):
    import time

    def get_values(key):
        # Get values
        params = Parameters()
        hql = (
            """
            SELECT DISTINCT map.value
            FROM Annotation ann
            JOIN ann.mapValue map
            WHERE map.name = %s
        """
            % f"'{key}'"
        )
        qs = conn.getQueryService()
        return [
            result[0].val for result in qs.projection(hql, params, conn.SERVICE_OPTS)
        ]

    start = time.time()
    selected_tags = [int(x) for x in request.GET.getlist("selectedTags")]
    excluded_tags = [int(x) for x in request.GET.getlist("excludedTags")]
    selected_keys_values = []
    selectable_values = {}

    empty_keys = False
    i = 0
    # loop over all selected keys
    while not empty_keys:
        selected_key = str(request.GET.get(f"selectedKey{i}", "1"))
        # no more keys are selected
        if selected_key == "1":
            empty_keys = True
        else:
            if selected_key != "_Choose Key_":
                selected_key_value = {}
                selected_values = [str(x) for x in request.GET.getlist(f"selectedValue{i}", "1")]
                if len(selected_values) == "0" or \
                        (len(selected_values) == 1 and
                         (selected_values[0] == "_Choose Value_" or selected_values[0] == "1")):
                    selected_key_value[selected_key] = []
                    selectable_values[f"selectedValue{i}"] = get_values(selected_key)
                else:
                    selected_key_value[selected_key] = selected_values
                    selectable_values[f"selectedValue{i}"] = None
                selected_keys_values.append(selected_key_value)
            else:
                selectable_values[f"selectedValue{i}"] = []
        i += 1

    selected_namespaces = [f"'{x}'" for x in request.GET.getlist("selectedNamespaces")]

    operation = request.GET.get("operation")

    # validate experimenter is in the active group
    active_group = (
        request.session.get("active_group")
        or conn.getEventContext().groupId
    )
    service_opts = conn.SERVICE_OPTS.copy()
    service_opts.setOmeroGroup(active_group)

    def get_annotated_obj(obj_type, in_ids, excl_ids, key_values, ns_list):
        # Get the images that match
        params = Parameters()
        params.map = {}

        tag_query = ""
        key_query = ""
        namespace_query = ""

        # get included tags
        if len(in_ids) > 0:
            tag_query = "link.child.id in (%s)" % ",".join([str(x) for x in in_ids])

        # get key-values
        if len(key_values) > 0:
            if tag_query != "":
                key_query = "or "
            where_clause = []
            for kv in key_values:
                for k, v in kv.items():
                    if len(v) > 0:
                        where_clause.append("(mv.name in ('%s') and mv.value in (%s))" % (k, ",".join([f"'{x}'" for x in v])))
                    else:
                        where_clause.append("(mv.name in ('%s'))" % list(kv.keys())[0])
            key_query += "link.child.id in (select distinct a.id from " \
                       "Annotation a join a.mapValue mv where %s)" % (" or ".join(where_clause))

            # get namespaces
            if len(ns_list) > 0:
                namespace_query = " and link.child.ns in (%s)" % ",".join([str(x) for x in ns_list])

        hql = ("select link.parent.id from %sAnnotationLink link where %s %s %s"
               % (obj_type, tag_query, key_query, namespace_query))

        # get excluded tags
        if len(excl_ids) > 0:
            params.map["ex_ids"] = rlist([rlong(o) for o in set(excl_ids)])
            hql += (" and link.parent.id not in "
                    "(select link.parent.id from %sAnnotationLink link "
                    "where link.child.id in (:ex_ids)) " % (obj_type))

        hql += " group by link.parent.id"
        if operation == "AND":
            hql += f" having count (distinct link.child) = {(len(set(in_ids)) + len(key_values))}"

        qs = conn.getQueryService()
        return [x[0].getValue() for x in qs.projection(hql,
                                                       params,
                                                       service_opts)]

    context = {}
    html_response = ""
    remaining = set([])

    manager = {"containers": {}}
    preview = False
    count_d = {}
    if selected_tags or selected_keys_values:
        image_ids = get_annotated_obj("Image", selected_tags,
                                      excluded_tags, selected_keys_values, selected_namespaces)
        count_d["image"] = len(image_ids)

        dataset_ids = get_annotated_obj("Dataset", selected_tags,
                                        excluded_tags, selected_keys_values, selected_namespaces)
        count_d["dataset"] = len(dataset_ids)

        project_ids = get_annotated_obj("Project", selected_tags,
                                        excluded_tags, selected_keys_values, selected_namespaces)
        count_d["project"] = len(project_ids)

        screen_ids = get_annotated_obj("Screen", selected_tags,
                                       excluded_tags, selected_keys_values, selected_namespaces)
        count_d["screen"] = len(screen_ids)

        plate_ids = get_annotated_obj("Plate", selected_tags,
                                      excluded_tags, selected_keys_values, selected_namespaces)
        count_d["plate"] = len(plate_ids)

        well_ids = get_annotated_obj("Well", selected_tags,
                                     excluded_tags, selected_keys_values, selected_namespaces)
        count_d["well"] = len(well_ids)

        acquisition_ids = get_annotated_obj("PlateAcquisition",selected_tags,
                                            excluded_tags, selected_keys_values, selected_namespaces)
        count_d["acquisition"] = len(acquisition_ids)

        if image_ids:
            images = conn.getObjects("Image", ids=image_ids)
            manager["containers"]["image"] = list(images)

        if dataset_ids:
            datasets = conn.getObjects("Dataset", ids=dataset_ids)
            manager["containers"]["dataset"] = list(datasets)

        if project_ids:
            projects = conn.getObjects("Project", ids=project_ids)
            manager["containers"]["project"] = list(projects)

        if screen_ids:
            screens = conn.getObjects("Screen", ids=screen_ids)
            manager["containers"]["screen"] = list(screens)

        if plate_ids:
            plates = conn.getObjects("Plate", ids=plate_ids)
            manager["containers"]["plate"] = list(plates)

        if well_ids:
            wells = []
            for w in conn.getObjects("Well", ids=well_ids):
                w.name = f"{w.getParent().name} - {w.getWellPos()}"
                wells.append(w)
            manager["containers"]["well"] = wells

        if acquisition_ids:
            acquisitions = conn.getObjects(
                "PlateAcquisition", ids=acquisition_ids
            )
            manager["containers"]["acquisition"] = list(acquisitions)

        manager["c_size"] = sum(count_d.values())
        if manager["c_size"] > 0:
            preview = True

        context["manager"] = manager

        html_response = render_to_string(
            "omero_tagsearch/search_details.html", context
        )

        middle = time.time()

        def get_objects_annotations(obj_type, oids):
            # Get the images that match
            params = Parameters()
            params.map = {}
            hql = (
                "select distinct link.child.id " +
                "from %sAnnotationLink link " % obj_type
            )
            if operation == "AND":
                hql += "where link.parent.id in (:oids)"
                params.map["oids"] = rlist([rlong(o) for o in oids])

            qs = conn.getQueryService()
            return [
                result[0].val for result in qs.projection(hql,
                                                          params,
                                                          service_opts)
            ]

        # Calculate remaining possible tag navigations
        # TODO Compare subquery to pass-in performance
        # sub_hql = """
        #     SELECT link.parent.id
        #     FROM ImageAnnotationLink link
        #     WHERE link.child.id IN (:oids)
        #     GROUP BY link.parent.id
        #     HAVING count (link.parent) = %s
        # """ % len(selected_tags)
        # hql = """
        #     SELECT DISTINCT link.child.id
        #     FROM ImageAnnotationLink link
        #     WHERE link.parent.id IN (%s)
        # """ % sub_hql

        if operation == "AND":
            if image_ids:
                remaining.update(get_objects_annotations("Image",
                                                         image_ids))
            if dataset_ids:
                remaining.update(get_objects_annotations("Dataset",
                                                         dataset_ids))
            if project_ids:
                remaining.update(get_objects_annotations("Project",
                                                         project_ids))
            if well_ids:
                remaining.update(get_objects_annotations("Well",
                                                         well_ids))
            if acquisition_ids:
                remaining.update(
                    get_objects_annotations("PlateAcquisition",
                                            acquisition_ids))
            if plate_ids:
                remaining.update(get_objects_annotations("Plate",
                                                         plate_ids))
            if screen_ids:
                remaining.update(get_objects_annotations("Screen",
                                                         screen_ids))

        end = time.time()
        logger.info(
            "Tag Query Times. Preview: %ss, Remaining: %ss, Total:%ss"
            % ((middle - start), (end - middle), (end - start))
        )

    # Return the navigation data and the html preview for display
    # return {"navdata": list(remaining), "html": html_response}
    return HttpResponse(
        json.dumps(
            {
                "navdata": list(remaining),
                "values": selectable_values,
                "preview": preview,
                "count": count_d,
                "html": html_response,
            }
        ),
        content_type="application/json",
    )
