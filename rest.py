import mimetools
import json
import base64
import cookielib
import pprint
import datetime
from urllib2 import Request as URLRequest, BaseHandler, HTTPCookieProcessor, build_opener, install_opener, HTTPError
import os
import re
import time
import socket
import urllib

class   RestRequest( object ):
  __slots__ = (
    'path',
    'content',
    'http_method',
  )
  
  def   __init__( self, path, content = None, http_method = None ):
    if not path.startswith('/'):
      path = '/' + path
    
    self.path         = path
    self.content      = content
    self.http_method  = http_method

class   RestType (object ):
  __slots__ = (
    'name',
    'description',
    'attributes',
    'methods',
    'is_embedded',
  )  
  #//-------------------------------------------------------//  
  def   __new__( cls, raw_dict ):
    if 'type' in raw_dict:
      return RestEnumType( raw_dict )    
    if isString( raw_dict ):
      try:
        return _REST_TYPES[ raw_dict ]
      except KeyError:
        raise Exception("Unknown REST object type: '%s'" % (raw_dict,))    
    return super(RestType, cls).__new__( cls )
  #//-------------------------------------------------------//  
  def   __init__(self, raw_dict ):    
    if isString( raw_dict ):
      return    
    self.description = raw_dict.get('description', '')
    self.name = raw_dict['name']
    self.attributes = {}
    self.methods = {}    
    for arg in raw_dict.get('attributes', tuple() ):
      arg = RestValue( arg )
      self.attributes[ arg.name ] = arg    
    for action in raw_dict.get('actions', tuple() ):
      method = RestMethod( self, action )
      self.methods[ method.name ] = method    
    self.is_embedded = 'id' not in self.attributes    
    _REST_TYPES[ self.name ] = self
  #//-------------------------------------------------------//  
  def   _setType( self ):
    for attr in self.attributes.values():
      attr._setType()    
    for method in self.methods.values():
      method._setType()
  #//-------------------------------------------------------//  
  def   load( self, raw, connection, instance = None ):    
    if instance is None:
      instance = RestInstance( self, connection )    
    if isString( raw ):
      instance.id = raw
    else:
      for name, attr in self.attributes.items():
        value = raw.get( name, None)
        if value is not None:
          setattr( instance, name, attr.load( value, connection ) )
        else:
          try:
            delattr( instance, name )
          except AttributeError:
            pass    
    return instance
  #//-------------------------------------------------------//
  def   dump( self, instance, only_id = False ):
    raw = {}    
    if not isinstance( instance, dict ):
      instance = instance.__dict__    
    for name, attr in self.attributes.items():
      value = instance.get( name, None )      
      if value is not None:
        if (self.is_embedded or not only_id) or (name == 'id'):
          raw[ name ] = attr.dump( value, only_id = only_id )    
    return raw
  #//-------------------------------------------------------//  
  def   setFieldType(self, attr_name, value_type ):
    attr = self.attributes[ attr_name ]
    attr.setValueType( value_type )  
  #//-------------------------------------------------------//  
  def   getFields( self ):
    if not self.attributes:
      return ""
    
    # attributes = map( operator.attrgetter( 'name' ), self.attributes.values() )
    
    # if fields:
    #   if not isinstance( fields, (tuple,list)):
    #     fields = (fields,)
    #   
    #   attributes.intersection_update( fields )
    # 
    # if nofields:
    #   if not isinstance( nofields, (tuple,list)):
    #     nofields = (nofields,)
    #   
    #   attributes.difference_update( nofields )
    return "&fields=" + ','.join( self.attributes )
  #//-------------------------------------------------------//  
  def   removeFields(self, fields ):
    if not fields:
      return    
    if not isinstance( fields, (tuple,list)):
      fields = (fields,)    
    for field in fields:
      try:
        del self.attributes[ field ]
      except KeyError:
        pass
  #//-------------------------------------------------------//  
  def   list( self, connection, **kw ):    
    path = "/api/types/%s/instances?visibility=engineering" % (self.name,)    
    path += self.getFields()    
    filter = []
    for name, value in kw.items():      
      if isinstance( value, (str,UStr,dict,list,tuple) ) and (not value):
        continue      
      try:
        value = _dumpValue( self.attributes[name].rest_type, value, only_id = True )
      except KeyError:
        raise Exception( "Unknown filter attribute '%s'" % (name,) )      
      for k, v in _getFilters( [name], value ):
        filter.append( "%s eq %s" % (k, v ) )      
    if filter:
      path += "&filter=" + urllib.quote(' AND '.join( filter ))    
    raw = connection.sendJsonRequest( RestRequest( path, http_method = "GET" ), debug = True )    
    instances = []
    for raw_instance in raw['entries']:
      instance = self.load( raw_instance['content'], connection )
      instance._connection = connection      
      instances.append( instance )    
    return instances    
    
class   RestConnection:
    
  def __init__(self, address, user, password):
    
    if user:
      domain, sep, login = user.partition('/')
      if not login:
        user = 'Local/' + domain
    
    self.request_url  = 'https://' + address
    self.user         = user
    self.password     = password    
    self.connect()
 
  def   connect(self):
    self.csrf_token = None
    self.__login()    
    # get EMC-CSRF-TOKEN
    request = self.makeJsonRequest( RestRequest('/api/types/loginSessionInfo/instances') )
    response = self.url_opener.open( request )
    self._saveCsrfToken( response )
  def  __login( self ):
    url = self.request_url + '/index.html'
    
    cj = cookielib.CookieJar()
    url_opener = build_opener( HTTPCookieProcessor(cj) )
    self.url_opener = url_opener
    response = url_opener.open( URLRequest( url ) )
    location = response.headers.get('Location', None)
    if location:
      request = URLRequest( location )
    else: # already open
      request = URLRequest( url )
    request.add_header('X-EMC-REST-CLIENT', 'TRUE')
    request.add_header('Authorization', b'Basic ' + base64.b64encode( self.user + b':' + self.password ))
    request.add_header('WWW_Authenticate', 'Basic realm="Security Realm"')
    # login and store cookuies
    try:
      url_opener.open( request )
    except HTTPError as err:
      if err.code == 401:
        request.add_header('Authorization', b'Basic ' + base64.b64encode( self.user + b':' + "Password123#" ))
        url_opener.open( request )
   
  def   makeUploadRequest( self, path, filename, data ):
    if not path.startswith('/'):
      path = '/' + path
    request = URLRequest( self.request_url + path )
    BOUNDARY = mimetools.choose_boundary()
    CRLF = '\r\n'
    content = []
    content.append('--' + BOUNDARY)
    content.append('Content-Disposition: form-data; name="upload"; filename="%s"' % (filename) )
    content.append('Content-Type: application/octet-stream')
    content.append('')
    content.append(data)
    content.append('--' + BOUNDARY + '--')
    content = CRLF.join( content )
    content_type = 'multipart/form-data; boundary=%s' % BOUNDARY
    request.add_unredirected_header('Content-Type', content_type)
    request.add_unredirected_header('Content-Length', str(len(content)))
    request.add_data( content )
    return request
   
  def   makeDownloadRequest( self, path ):
    if not path.startswith('/'):
      path = '/' + path    
    return URLRequest( self.request_url + path )
  
  #//-------------------------------------------------------//
  
  def   makeJsonRequest( self, rest_request ):
    url = self.request_url + rest_request.path
    request = URLRequest( url )
    request.add_header('Content-Type', 'application/json')
    request.add_header('Accept', 'application/json')
    self._addEmcHeaders( request )
    if rest_request.content:
      if isinstance( rest_request.content, dict ):
        content = json.dumps( rest_request.content )
      else:
        content = rest_request.content
      request.add_data( content )
    if rest_request.http_method:
      request.get_method = lambda http_method = str(rest_request.http_method): http_method    
    return request
  
  #//-------------------------------------------------------//
  
  def   _addEmcHeaders(self, request ):
    request.add_header('X-EMC-REST-CLIENT', 'TRUE')    
    if self.csrf_token:
      request.add_header('EMC-CSRF-TOKEN', self.csrf_token )
  
  #//-------------------------------------------------------//
  
  def   _saveCsrfToken(self, response ):
    csrf_token = response.headers.get('EMC-CSRF-TOKEN', None )
    if csrf_token and (self.csrf_token != csrf_token):
      print("EMC-CSRF-TOKEN: %s" % (csrf_token,))
      self.csrf_token = csrf_token
  
  #//-------------------------------------------------------//
  
  def   sendRequest( self, request, timeout = None, log = False, log_data  = False):    
    if log:      
      print(">" * 32)
      print("[%s]>> REQUEST: %s, method: %s, data:" % (datetime.datetime.now().time(), request.get_full_url(), request.get_method()) )
      if log_data:
        pprint.pprint( request.get_data() )    
    if timeout is None:
      timeout = 3600    
    try:
      response = self.url_opener.open( request, timeout = timeout )
    except HTTPError as err:
      if err.code == 404:
        raise RestNotFoundError( "Wrong URL: %s" % (request.get_full_url(),) )      
      elif err.code == 401:
        try:
          self.connect()          
          req = URLRequest( request.get_full_url(), request.get_data(), request.headers )
          req.get_method = request.get_method
          self._addEmcHeaders( req )          
          response = self.url_opener.open( req, timeout = timeout )
        except HTTPError as err:
          raise RestJsonError( err.fp.read() )
      else:
        raise RestJsonError( err.fp.read() )    
    self._saveCsrfToken( response )    
    return response
  
  #//-------------------------------------------------------//
  
  def   sendJsonRequest( self, request, timeout = None, debug = False ):    
    if isinstance( request, RestRequest ):
        request = self.makeJsonRequest( request )    
    response = self.sendRequest( request, timeout = timeout, log = debug, log_data = debug )    
    response = response.read()
    response = response.strip()    
    if debug:
      print("<" * 32)
      print("[%s]<< RESPONSE:" % (datetime.datetime.now().time(),))    
    if not response:
      print(None)
      return {}    
    try:
      response = json.loads( response, encoding = 'utf-8' )
    except Exception as err:
      raise Exception( response )    
    if debug:
      pprint.pprint( response )    
    return response
  
  #//-------------------------------------------------------//
  
  def   sendUploadRequest( self, path, filename, content, timeout = None ):
    request = self.makeUploadRequest( path, filename, content )
    return self.sendRequest( request, timeout = timeout, log = True, log_data = False )
  
  #//-------------------------------------------------------//
  
  def   sendDownloadRequest( self, path, timeout = None ):
    request = self.makeDownloadRequest( path )
    return self.sendRequest( request, timeout = timeout, log = True, log_data = False )
    
    
connection = RestConnection('10.109.221.120', 'admin' , 'Password123!')
initRestTypes( connection )
try:
  UStr = unicode
except NameError:
  UStr = str

def   isString( value ):
    return isinstance( value, (str,UStr) )


class   IpAddressString (str):
  """
  Class expresses type of string where case doesn't metter.
  """
  def     __new__(cls, value = None ):
    
    if type(value) is cls:
      return value
    
    if value is None:
      value = ''
    else:
      value = str(value).lower()
    
    addr, sep, prefix = value.rpartition('/')
    if not addr:
      addr = prefix
      prefix = None
    
    addr = IpAddressString.__normAddress(addr)
    if prefix:
      value = '/'.join([addr, prefix])
    else:
      value = addr
    
    self = super(IpAddressString, cls).__new__(cls, value)
    self._address = addr
    self._prefix = prefix
    return self
  
  @staticmethod
  def   __normAddress( addr ):
    try:
      n = socket.inet_pton( socket.AF_INET, addr )
      addr = socket.inet_ntop( socket.AF_INET, n)
    except socket.error:
      try:
        n = socket.inet_pton( socket.AF_INET6, addr )
        addr = socket.inet_ntop( socket.AF_INET6, n)
      except socket.error:
        addr = addr.lower()
    
    return str(addr)
  
  def   __hash__(self):
    return hash(self._address)
    
  def   __eq__( self, other):
    
    other = IpAddressString(other)
    
    if self._address == other._address:
      if self._prefix and other._prefix:
        return self._prefix == other._prefix
      
      return True
    
    return False
  
  def   __ne__( self, other):
    return not self.__eq__( other )

_REST_TYPES = {

  'String':     UStr,
  'Float':      float,
  'Boolean':    bool,
  'Integer':    int,
  'DateTime':   UStr,
  'IPAddress':  IpAddressString,
  
  'HealthEnum':         int,  # workaround for REST API issue, type is not listed
  'ACEAccessTypeEnum':  int,  # workaround for REST API issue, type is not listed
  'ACEAccessLevelEnum': int,  # workaround for REST API issue, type is not listed
}
    
    
for eth in RestInstance('ioModule', connection ).list():
    pprint.pprint( eth.dump() )
    
pool = RestInstance('pool', connection ).list()[0]
sp = RestInstance('storageProcessor', connection).list()[0]