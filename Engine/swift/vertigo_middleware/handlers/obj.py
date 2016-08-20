from swift.common.swob import HTTPMethodNotAllowed, Response
from swift.common.utils import public
import time

from vertigo_middleware.handlers import VertigoBaseHandler
from vertigo_middleware.common.utils import get_microcontroller_list, set_microcontroller, delete_microcontroller, get_microcontroller_dict


class VertigoObjectHandler(VertigoBaseHandler):

    def __init__(self, request, conf, app, logger):
        super(VertigoObjectHandler, self).__init__(
            request, conf, app, logger)

    def _parse_vaco(self):
        _, _, acc, cont, obj = self.request.split_path(
            5, 5, rest_with_last=True)
        return ('v1', acc, cont, obj)

    @property
    def is_slo_get_request(self):
        """
        Determines from a GET request and its  associated response
        if the object is a SLO
        """
        return self.request.params.get('multipart-manifest') == 'get'

    def handle_request(self):
        if hasattr(self, self.request.method):
            try:
                handler = getattr(self, self.request.method)
                getattr(handler, 'publicly_accessible')
            except AttributeError:
                return HTTPMethodNotAllowed(request=self.request)
            return handler()
        else:
            return self.request.get_response(self.app)
            #return HTTPMethodNotAllowed(request=self.request)

    def _call_storlet_gateway_on_put(self, req, storlet_list):
        req = self.storlet_gateway.execute_storlets(req, storlet_list)
        req.headers.pop('Storlet-Executed')
        return req

    def _call_storlet_gateway_on_get(self, resp, storlet_list):
        return self.storlet_gateway.execute_storlets(resp, storlet_list)

    @public
    def GET(self):
        """
        GET handler on Object
        """
        response = self.request.get_response(self.app)
        
        start = time.time()
        mc_list = get_microcontroller_list(self)
        
        if mc_list:
            self.logger.info('Vertigo - There are microcontrollers' +
                             ' to execute: ' + str(mc_list))
            self.request.headers['X-Current-Server'] = self.execution_server
            self._setup_docker_gateway(response)
            # Go to run the micro-controller(s)
            storlet_list = self.mc_docker_gateway.execute_microcontrollers(mc_list)

            self.logger.info('Vertigo - Microcontroller executed correctly')
            # Go to run the Storlet(s) whether the microcontroller
            # sends back any.

            if storlet_list:
                self.logger.info('Vertigo - Go to execute Storlets: '+str(storlet_list))
                self._setup_storlet_gateway()
                response = self.apply_storlet_on_get(response, storlet_list)
            else:
                self.logger.info('Vertigo - No Storlets to execute')
        else:
            self.logger.info('Vertigo - No Microcontrollers to execute')
            
        end = time.time() - start
        self.logger.info('---')
        self.logger.info('Total execution time: ' + str(int(round(end * 1000))) + 'ms')
        self.logger.info('---')
        # f = open('/home/lab144/josep/middleware_get_tstamp.log','a')
        # f.write(str(end)+'\n') # python will convert \n to os.linesep
        # f.close()

        return response

    @public
    def PUT(self):
        """
        PUT handler on Object
        """
        if self.is_trigger_assignation:
            # Only enters here when a user assign a micro-controller to an object
            trigger, micro_controller = self.get_mc_assignation_data()
            
            try:
                set_microcontroller(self, trigger, micro_controller)
                msg = 'Vertigo - Microcontroller "' + micro_controller + \
                    '" correctly assigned to the "'+ trigger + '" trigger.\n'
            except ValueError as e:
                msg = e.args[0]

            self.logger.info(msg)
            return Response(body = msg, headers = {'etag':''},
                            request = self.request)
            
        if self.is_trigger_deletion:
            trigger, micro_controller = self.get_mc_deletion_data()
            
            try:
                delete_microcontroller(self, trigger, micro_controller)
                msg = 'Vertigo - Microcontroller "' + micro_controller +\
                    '" correctly removed from the "'+ trigger + '" trigger.\n'
            except ValueError as e:
                msg = e.args[0]

            return Response(body = msg, headers = {'etag':''},
                            request = self.request)   
        else:
            return self.request.get_response(self.app)
      
    @public
    def HEAD(self):
        """
        HEAD handler on Object
        """
        original_resp = self.request.get_response(self.app)
        mc_dict = get_microcontroller_dict(self)
        if mc_dict:
            for trigger in mc_dict.keys():
                if not mc_dict[trigger]:
                    del mc_dict[trigger]
            original_resp.headers['Vertigo-Microcontroller'] = mc_dict

        return original_resp
    