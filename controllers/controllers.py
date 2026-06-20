# -*- coding: utf-8 -*-
# from odoo import http


# class ItParc(http.Controller):
#     @http.route('/it_parc/it_parc', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/it_parc/it_parc/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('it_parc.listing', {
#             'root': '/it_parc/it_parc',
#             'objects': http.request.env['it_parc.it_parc'].search([]),
#         })

#     @http.route('/it_parc/it_parc/objects/<model("it_parc.it_parc"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('it_parc.object', {
#             'object': obj
#         })

