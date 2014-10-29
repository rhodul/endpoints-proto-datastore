# If you have not yet seen the source in keys_with_ancestors/main.py,
# please take a look.

# In this sample we define ChildEndpointsModel class that can be used to model
# simple child Entity, where both parent and child keys are left alone for NDB
# to generate.

# We define an extra model MyParent to hold all the data for the ancestors
# being used (though this is not strictly necessary, an ancestor key does not
# need to exist in the datastore to be used). In addition, since we will
# be requiring that a MyParent entity exists to be used as an ancestor, we
# provide a method MyParentInsert to allow API users to create parent objects.

import endpoints

from google.appengine.ext import ndb
from protorpc import remote
from protorpc import messages

# See matching_queries_to_indexes/main.py for reference on this import.
from endpoints_proto_datastore.ndb import EndpointsAliasProperty
from endpoints_proto_datastore.ndb import EndpointsModel


class ChildEndpointsModel(EndpointsModel):
  """Base child model class."""

  # This property must be set by an inheritor
  # to a class of a model that represents this model's
  # parent entity.
  parent_model_class = None

  # These values are placeholders to be used when a key is created;
  # the _parent will be used as the ancestor and the _id as the ID.
  # For example: ndb.Key(parent_class, _parent, self.__class__, _id)
  # Since these values will be set by alias properties which are not set
  # simultaneously, we need to hold them around until both are present before
  # we can create a key from them.
  _parent = None
  _id = None

  # This is a helper method that will set the key on the entity only if both the
  # parent and ID are present. It will be used by property setters that provide
  # values for _parent and _id.
  def SetKey(self):
    # This function gets called by ParentSet() and maybe by IdSet().
    # IdSet() will only be called if the REST client supplied child id,
    # which means the client wants to work with existing child entity.

    # If _parent ID is present, let's set the key, so we know who the parent
    # is.
    if self._parent is not None:
      # We don't mind _id being None. Inserting a partial key,
      # ndb.Key(ParentModel, 5629499534213120, ChildModel, None),
      # will generate child's id, so we end up with
      # ndb.Key(ParentModel, 5629499534213120,
      #         ChildModel, 4629846532513666).
      # We end up in this situation when child id is not supplied by REST client
      # in the POST, which causes new child entity to be created
      # (see the 'if' below).
      self._key = key = ndb.Key(self.__class__.parent_model_class,
                                self._parent, self.__class__, self._id)
      if self._id is not None:
        # Child id has been supplied by REST client, which means
        # that it is an attempt to work with existing child entity.
        # We will attempt to update the entity.
        self.UpdateFromKey(key)

  # This is a helper method that will set the _parent and _id values using the
  # entity key, if it exists. It will be used by property getters that retrieve
  # the current values of _parent and _id.
  def SetParts(self):
    # If there is no key, nothing can be set.
    if self.key is not None:
      # If there are not two tuples in the key pairs, a ValueError will occur.
      parent_pair, id_pair = self.key.pairs()
      # Each pair in key pairs will be a tuple (model kind, value) where model
      # kind is a string representing the name of the model and value is the
      # actual string or integer ID that was set.
      self._parent = parent_pair[1]
      self._id = id_pair[1]

  # This is a setter which will be used by the alias property "parent". This
  # method will be called when parent is set from a ProtoRPC request.
  def ParentSet(self, value):
    self._parent = value
    # After setting the value, we must make sure the parent exists before
    # it can be used as an ancestor.
    if ndb.Key(self.__class__.parent_model_class, value).get() is None:
      # If the Parent key does not correspond to an entity in the datastore,
      # we return an HTTP 404 Not Found.
      raise endpoints.NotFoundException('Parent with id %s does not exist.'
                                        % value)

    # The helper method SetKey is called to set the entity key if the _id has
    # also been set already.
    self.SetKey()

    # If the "parent" property is used in a query method, we want
    # the ancestor of the query to be the parent key.
    self._endpoints_query_info.ancestor = \
        ndb.Key(self.__class__.parent_model_class, value)

  # This EndpointsAliasProperty is used to get and set a parent for our entity
  # key. It is required, meaning that a value must always be set if the
  # corresponding field is contained in a ProtoRPC message schema.
  @EndpointsAliasProperty(setter=ParentSet, required=True,
                          property_type=messages.IntegerField)
  def parent(self):
    # If _parent has not already been set on the entity, try to set it.
    if self._parent is None:
        # Using the helper method SetParts, _parent will be set if a valid key
        # has been set on the entity.
        self.SetParts()

    return self._parent

  # This is a setter which will be used by the alias property "id". This
  # method will be called when id is set from a ProtoRPC request. This replaces
  # the helper property "id" provided by EndpointsModel, but does not use any
  # of the functionality from that method.
  def IdSet(self, value):
    self._id = value
    # The helper method SetKey is called to set the entity key if the _parent
    # has also been set already.
    self.SetKey()

  # This EndpointsAliasProperty is used to get and set an id value for our
  # entity key. It is required, meaning that a value must always be set if the
  # corresponding field is contained in a ProtoRPC message schema.
  @EndpointsAliasProperty(setter=IdSet, required=True,
                          property_type=messages.IntegerField)
  def id(self):
    # If _id has not already been set on the entity, try to set it.
    if self._id is None:
      # Using the helper method SetParts, _id will be set if a valid key has
      # been set on the entity.
      self.SetParts()
    return self._id


class MyParent(EndpointsModel):
  # As in simple_get/main.py, by setting _message_fields_schema, we can set
  # a custom ProtoRPC message schema. We added the built in ID property
  # and ignore the NDB property updated.
  _message_fields_schema = ('id', 'name')

  name = ndb.StringProperty(required=True)
  updated = ndb.DateTimeProperty(auto_now=True)


# Here we inherit from the ChildEnpointModel base class
# that has all the wiring for dealing with parent ID
class MyModel(ChildEndpointsModel):
  # we need to tell ChildEndpointsModel which EndpointsModel
  # defines parent Entity type
  parent_model_class = MyParent

  attr1 = ndb.StringProperty()
  attr2 = ndb.StringProperty()
  created = ndb.DateTimeProperty(auto_now_add=True)
  modified_by = ndb.UserProperty(required=True)


@endpoints.api(name='myapi', version='v1', description='My Little API')
class MyApi(remote.Service):

  # This method is not defined in any of the previous examples; it allows a
  # parent entity to be inserted so that it can be used as an ancestor. Since
  # the ProtoRPC message schema for MyParent is a single field "name", this
  # will be all that is contained in the request and the response.
  @MyParent.method(request_fields=('name',),
                   path='myparent',
                   http_method='POST',
                   name='myparent.insert')
  def MyParentInsert(self, my_parent):
    # Though we don't actively change the model passed in, the value
    # of updated is set to the current time.
    my_parent.put()
    return my_parent

  # Since we require MyModel instances also have a MyParent ancestor,
  # we include "parent" in the request path by setting
  # path='mymodel/{parent}'.
  # Unlike in keys_with_ancestors/main.py, we want a datastore to generate
  # child ID, therefore we do not include it in the request body.
  @MyModel.method(user_required=True,
                  request_fields=('attr1', 'attr2'),
                  path='mymodel/{parent}',
                  http_method='POST',
                  name='mymodel.insert')
  def MyModelInsert(self, my_model):
    my_model.modified_by = endpoints.get_current_user()
    my_model.put()
    return my_model

  # To make sure queries have a specified ancestor, we use the alias property
  # "parent" which we defined on MyModel and specify query_fields equal to
  # ('parent',). To specify the parent in the query, it is included in the path
  # as it was in MyModelInsert. So no query parameters will be required, simply
  # a request to
  #   .../mymodels/someparentID
  # where ... is the full path to the API.
  @MyModel.query_method(query_fields=('parent',),
                        path='mymodels/{parent}',
                        name='mymodel.list')
  def MyModelList(self, query):
    return query

  # To update MyModel entity, we need to identify it by both {parent}
  # and {id}.
  @MyModel.method(user_required=True,
                  request_fields=('attr1', 'attr2'),
                  path='mymodel/{parent}/{id}',
                  http_method='PUT',
                  name='mymodel.update')
  def MyModelUpdate(self, my_model):
    if not my_model.from_datastore:
      raise endpoints.BadRequestException(
          'MyModel %s with parent %s does not exist.' %
          (my_model.id, my_model.parent.id))

    my_model.modified_by = endpoints.get_current_user()
    my_model.put()
    return my_model

application = endpoints.api_server([MyApi], restricted=False)
