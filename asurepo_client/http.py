import logging
import types

import filelike.wrappers
import poster
from poster.encode import MultipartParam

LOG = logging.getLogger('asurepo.client.http')

def multipart_encode(params, boundary=None):
    '''
    Extends poster.encode.multipart_encode to allow a map of constructor
    arguments for poster.encode.MultipartParam to be specified in lieue of a
    file in the standard {partname: file} or [(partname, file)].  Accounts for
    the fact that the specified filelike may not support seek() or tell(), which
    are needed to determine Content-Length, and will retry in that situation
    with an appropriately wrapped filelike object.
    '''
    if hasattr(params, 'items'):
        params = params.items()

    def transform(param):
        if type(param) == MultipartParam:
            return param
        else:
            name, content = param
            if type(content) == types.DictType:
                try:
                    return MultipartParam(name, **content)
                except ValueError as e:
                    if e.message == 'Could not determine filesize':
                        if 'fileobj' in content:
                            content['fileobj'] = filelike.wrappers.Buffer(content['fileobj'])
                            return MultipartParam(name, **content)
                    raise
            else:
                try:
                    return MultipartParam.from_params([param])[0]
                except ValueError as e:
                    if e.message == 'Could not determine filesize':
                        wrappedcontent = filelike.wrappers.Buffer(content)
                        return MultipartParam.from_params([(name, wrappedcontent)])[0]
                    raise

    return poster.encode.multipart_encode([transform(p) for p in params],
                                          boundary)
