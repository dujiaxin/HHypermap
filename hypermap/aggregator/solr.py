import sys
import pysolr
import requests
import logging
import json

from django.conf import settings

from hypermap.aggregator.utils import layer2dict

SEARCH_URL = settings.REGISTRY_SEARCH_URL.split('+')[1]


LOGGER = logging.getLogger(__name__)


class SolrHypermap(object):

    def layers_to_solr(self, layers):
        """
        Sync n layers in Solr.
        """

        layers_dict_list = []
        layers_success_ids = []
        layers_errors_ids = []

        for layer in layers:
            layer_dict, message = layer2dict(layer)
            if not layer_dict:
                layers_errors_ids.append([layer.id, message])
                LOGGER.error(message)
            else:
                layers_dict_list.append(layer_dict)
                layers_success_ids.append(layer.id)

        layers_json = json.dumps(layers_dict_list)
        try:
            url_solr_update = '%s/solr/hypermap/update/json/docs' % SEARCH_URL
            headers = {"content-type": "application/json"}
            params = {"commitWithin": 1500}
            requests.post(url_solr_update, data=layers_json, params=params, headers=headers)
            LOGGER.info('Solr synced for the given layers')
        except Exception:
            message = "Error saving solr records: %s" % sys.exc_info()[1]
            layers_errors_ids.append([-1, message])
            LOGGER.error(message)
            return False, layers_errors_ids

        return True, layers_errors_ids

    def layer_to_solr(self, layer):
        """
        Sync a layer in Solr.
        """
        success = True
        message = 'Synced layer id %s to Solr' % layer.id

        layer_dict, message = layer2dict(layer)
        if not layer_dict:
            success = False
        else:
            layer_json = json.dumps(layer_dict)
            try:
                url_solr_update = '%s/solr/hypermap/update/json/docs' % SEARCH_URL
                headers = {"content-type": "application/json"}
                params = {"commitWithin": 1500}
                res = requests.post(url_solr_update, data=layer_json, params=params,  headers=headers)
                res = res.json()
                if 'error' in res:
                    success = False
                    message = "Error syncing layer id %s to Solr: %s" % (layer.id, res["error"].get("msg"))
            except Exception, e:
                success = False
                message = "Error syncing layer id %s to Solr: %s" % (layer.id, sys.exc_info()[1])
                LOGGER.error(e, exc_info=True)
        if success:
            LOGGER.info(message)
        else:
            LOGGER.error(message)
        return success, message

    def clear_solr(self, catalog="hypermap"):
        """Clear all indexes in the solr core"""
        solr_url = "{0}/solr/{1}".format(SEARCH_URL, catalog)
        solr = pysolr.Solr(solr_url, timeout=60)
        solr.delete(q='*:*')
        LOGGER.debug('Solr core cleared')

    def remove_layer(self, layer_uiid, catalog="hypermap"):
        """
        Remove a layer from Solr.
        """
        solr_url = "{0}/solr/{1}".format(SEARCH_URL, catalog)
        solr = pysolr.Solr(solr_url, timeout=60)
        solr.delete(q='uuid:%s' % layer_uiid)
        LOGGER.debug('Layer %s removed from Solr' % layer_uiid)

    def update_schema(self, catalog="hypermap"):
        """
        set the mapping in solr.
        :param catalog: core
        :return:
        """
        schema_url = "{0}/solr/{1}/schema".format(SEARCH_URL, catalog)
        print schema_url

        # create a special type to draw better heatmaps.
        location_rpt_quad_5m_payload = {
            "add-field-type": {
                "name": "location_rpt_quad_5m",
                "class": "solr.SpatialRecursivePrefixTreeFieldType",
                "geo": False,
                "worldBounds": "ENVELOPE(-180, 180, 180, -180)",
                "prefixTree": "packedQuad",
                "distErrPct": "0.025",
                "maxDistErr": "0.001",
                "distanceUnits": "degrees"
            }
        }
        requests.post(schema_url, json=location_rpt_quad_5m_payload)

        # now the other fields
        fields = [
            {"name": "abstract", "type": "string"},
            {"name": "area", "type": "tdouble"},
            {"name": "availability", "type": "string"},
            {"name": "bbox", "type": "location_rpt_quad_5m"},
            {"name": "domain_name", "type": "string"},
            {"name": "id", "type": "tlong", "required": True},
            {"name": "is_public", "type": "boolean"},
            {"name": "is_valid", "type": "boolean"},
            {"name": "last_status", "type": "boolean"},
            {"name": "layer_category", "type": "string"},
            {"name": "layer_date", "type": "tdate", "docValues": True},
            {"name": "layer_datetype", "type": "string"},
            {"name": "layer_id", "type": "tlong"},
            {"name": "layer_originator", "type": "string"},
            {"name": "layer_username", "type": "string"},
            {"name": "location", "type": "string"},
            {"name": "max_x", "type": "tdouble"},
            {"name": "max_y", "type": "tdouble"},
            {"name": "min_x", "type": "tdouble"},
            {"name": "min_y", "type": "tdouble"},
            {"name": "name", "type": "string"},
            {"name": "recent_reliability", "type": "tdouble"},
            {"name": "reliability", "type": "tdouble"},
            {"name": "service_id", "type": "tlong"},
            {"name": "service_type", "type": "string"},
            {"name": "srs", "type": "string", "multiValued": True},
            {"name": "tile_url", "type": "string"},
            {"name": "title", "type": "string"},
            {"name": "type", "type": "string"},
            {"name": "url", "type": "string"},
            {"name": "uuid", "type": "string", "required": True},
            {"name": "centroid_y", "type": "tdouble"},
            {"name": "centroid_x", "type": "tdouble"},
        ]

        headers = {
            "Content-type": "application/json"
        }

        for field in fields:
            data = {
                "add-field": field
            }
            requests.post(schema_url, json=data, headers=headers)
