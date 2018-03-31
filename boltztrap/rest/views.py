# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import json, math
from webtzite import mapi_func
from webtzite.connector import ConnectorBase
from mpcontribs.rest.views import Connector
from mpcontribs.io.core.components import Table
from mpcontribs.io.archieml.mpfile import MPFile
ConnectorBase.register(Connector)

@mapi_func(supported_methods=["POST", "GET"], requires_api_key=True)
def index(request, cid=None, db_type=None, mdb=None):
    try:
        response = None
        if request.method == 'GET':
            axes, dopings = ['<S>', '<σ>', '<S²σ>'], ['n', 'p']
            projection = dict(('content.data.{}'.format(k), 1) for k in axes)
            projection.update({'mp_cat_id': 1})
            docs = mdb.contrib_ad.query_contributions(
                {'project': 'boltztrap'}, projection=projection
            )
            response = {'text': []}
            response.update(dict((k, []) for k in axes))
            for doc in docs:
                d = doc['content']['data']
                for doping in dopings:
                    for idx, k in enumerate(axes):
                        if k in d and doping in d[k]:
                            value = d[k][doping]
                            value = float(value.split()[0])
                            if idx == 2:
                                value = math.log10(value)
                            response['text'].append(doc['mp_cat_id'])
                            response[k].append(value)

        elif request.method == 'POST':
            name = json.loads(request.body)['name']
            names = name.split('##')
            table_name = '{}({})'.format(names[0][1:-1], names[1][0])
            doc = mdb.contrib_ad.query_contributions(
                {'_id': cid}, projection={'_id': 0, 'content.{}'.format(table_name): 1}
            )[0]
            table = doc['content'].get(table_name)
            if table:
                table = Table.from_dict(table)
                x = [col.split()[0] for col in table.columns[1:]]
                y = list(table[table.columns[0]])
                z = table[table.columns[1:]].values.tolist()
                if not table_name.startswith('S'):
                    z = [[math.log10(float(c)) for c in r] for r in z]
                title = ' '.join([table_name, names[1].split()[-1]])
                response = {'x': x, 'y': y, 'z': z, 'type': 'heatmap', 'colorbar': {'title': title}}
    except Exception as ex:
        raise ValueError('"REST Error: "{}"'.format(str(ex)))
    return {"valid_response": True, 'response': response}


@mapi_func(supported_methods=["GET"], requires_api_key=False)
def table(request, db_type=None, mdb=None):
    try:
        page = int(request.GET.get('page', '1'))
        crit = {'project': 'boltztrap'}
        proj = {'content.data': 1, 'content.extra_data': 1, 'mp_cat_id': 1}
        total_count = mdb.contrib_ad.query_contributions(crit).count()
        last_id = None
        if page is not None and page > 1:
            limit = (page-1) * 20 # TODO page_size from where?
            ids = [d['_id'] for d in mdb.contrib_ad.query_contributions(crit, limit=limit)]
            last_id = ids[-1]
        docs, last_id = mdb.contrib_ad.query_paginate(crit, projection=proj, last_id=last_id)
        if not docs:
            raise Exception('No contributions found for Boltztrap Explorer!')

        items = []
        columns = ['##'.join(['general', sk]) for sk in ['mp-id', 'cid', 'formula']]
        keys, subkeys = {'<mₑᶜᵒⁿᵈ>': '[mₑ]', '<S>': '[μV/K]', '<σ>': '[(Ωms)⁻¹]', '<S²σ>': '[μW/(cmK²s)]'}, ['n', 'p']
        columns += ['##'.join([k, ' '.join([sk, keys[k]])]) for k in keys for sk in subkeys]

        for doc in docs:
            mpfile = MPFile.from_contribution(doc)
            mp_id = mpfile.ids[0]
            contrib = mpfile.hdata[mp_id]
            cid_url = '/'.join([
                request.build_absolute_uri(request.path).rsplit('/', 3)[0],
                'explorer', 'materials' , unicode(doc['_id'])
            ])
            mp_id_url = 'https://materialsproject.org/materials/{}'.format(mp_id)
            row = [mp_id_url, cid_url, contrib['extra_data']['pretty_formula']]
            row += [
                contrib['data'].get(k, {}).get(sk, '-').split()[0]
                for k in keys for sk in subkeys
            ]
            items.append(dict((k, v) for k, v in zip(columns, row)))

        per_page = len(items)
        total_pages = total_count/per_page
        if total_pages%per_page:
            total_pages += 1
        response = {
            'total_count': total_count, 'total_pages': total_pages, 'page': page,
            'last_page': total_pages, 'per_page': per_page, 'last_id': last_id, 'items': items
        }
    except Exception as ex:
        raise ValueError('"REST Error: "{}"'.format(str(ex)))
    return response