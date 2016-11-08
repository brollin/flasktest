from flask import Flask, jsonify, request, json
from collections import OrderedDict
import psycopg2
import sqlite3
import json
import sys
import os

def create_pgconn():

    # Initiate a connection to the postgres database
    return psycopg2.connect('dbname=postgres user=postgres')

def create_pgcurs(conn):

    # Create cursor in postgres database
    return conn.cursor()

def main():

    # Set up Flask server
    server = Flask('secret_fire')

    # Set up connection to postgres database
    pgconn = create_pgconn()
    pgcurs = create_pgcurs(pgconn)

    # Define members table column names and data types
    members_cols        = ('id','name','phone_no','email','years','playa_name','location','notes')
    members_cols_types  = ('int','text','text','text','int','text','text','text')
    members_table       = OrderedDict( zip( members_cols, members_cols_types ) )

    # Define projects table column names and data types
    projects_cols       = ('id','lead','description','budget')
    projects_cols_types = ('int','int','text','int')
    projects_table      = OrderedDict( zip( projects_cols, projects_cols_types ) )

    @server.route('/bentest')
    def home():

        # Create test page for /bentest
        display_text = """
        <title>Test Page</title>
        hello?! world?!...<p>
        """

        # Give the headers in the HTTP response
        return display_text + '<p><p>Headers:<p>' + request.headers.__str__().replace('\n','<p>')

    def check_database_inputs(change_dict, table):
        
        # Ensure that all columns in change_dict are in the table definition
        for col in change_dict.keys():
            if col not in table.keys():
                return 'Column %s not found in table!' % col

    # Class view_set creates a set of views for HTTP requests and routes them to a resource endpoint
    class ViewSet:
        
        # Constructor accepts options to determine the views to create
        def __init__( self, server, connection, cursor, endpoint, table, views=['GET','PUT','DELETE','POST'] ):

            # Store input parameter values into instance member variables
            self.server     = server
            self.connection = connection
            self.cursor     = cursor
            self.endpoint   = endpoint
            self.table      = table
            self.views      = views

            # Resource name is the last item in the relative endpoint path
            self.resource   = self.endpoint.split('/')[-1]

            # Primary key is the first column of the table
            self.pri_key    = self.table.keys()[0]
            
            assert len(self.resource) > 2, "The specified endpoint must be in the form: /path/from/host/to/resource"

            self.create_views()

        # Create views as specified for this instance
        def create_views( self ):
            
            if 'GET' in self.views:
                
                # GET method will return the JSON for the resource with that ID
                @self.server.route(self.endpoint + '/<int:id>', methods = ['GET'])
                def get_resource(id):
                    
                    try:
                        self.cursor.execute('SELECT * FROM ' + self.resource + ' WHERE ' + \
                            self.pri_key + ' = %s', (str(id),) )
                        record = self.cursor.fetchone()

                        if not record:
                            return 'Unsuccessful. No resource with ' + self.pri_key + ' %d found.' % id, 404

                        return jsonify( OrderedDict( zip( self.table.keys(), record ) ) )

                    except Exception as e:
                        return 'Unsuccessful. Error:\n' + str(e), 400

                self.get = get_resource

            elif 'PUT' in self.views:

                # PUT method will update the record with the supplied JSON info
                @self.server.route(self.endpoint + '/<int:id>', methods = ['PUT'])
                def put_resource(id):

                    try:
                        # Capture HTTP request data (JSON) and load into an update dictionary
                        update_dict = OrderedDict( json.loads( request.data ) )

                        # Ensure that if the id exists in update_dict, it matches the id provided in URL
                        if self.pri_key in update_dict:
                            if id != int( update_dict[self.pri_key] ):
                                return 'Error: ID does not match in body and URL', 400
                        # If the id is not in update_dict, add it
                        else:
                            update_dict['id'] = id

                        # Perform checks on dict describing values to be updated
                        inputs_check = check_database_inputs( update_dict, self.table )
                        if inputs_check:
                            return 'Error: ' + inputs_check, 400

                        # Execute and commit SQL command
                        sql = 'UPDATE ' + self.resource + '\nSET\n' + ',\n'.join([x + ' = %(' + x + ')s' for x in update_dict.keys()]) + '\nWHERE ' + self.pri_key + ' = %(id)s;'
                        self.cursor.execute( sql, update_dict )
                        self.connection.commit()

                        return 'Successfully updated resource with following SQL command:\n' + sql % update_dict, 201

                    except Exception as e:
                        return 'Unsuccessful. Error:\n' + str(e), 400

                self.put = put_resource

            elif 'DELETE' in self.views:

                # DELETE method will delete the record with the matching id
                @self.server.route(self.endpoint + '/<int:id>', methods = ['DELETE'])
                def delete_resource(id):

                    # Execute and commit SQL command
                    sql = 'DELETE FROM ' + self.resource + ' WHERE id = %s'
                    self.cursor.execute(sql, {self.pri_key:id} )
                    self.connection.commit()

                    return 'Successfully deleted resource with ' + self.pri_key + ' %d' % id, 201

                self.delete = delete_resource

            elif 'POST' in self.views:

                # POST method will create a record with the supplied JSON info
                @self.server.route(self.endpoint, methods = ['POST'])
                def post_resource(id):

                    try:
                        # Capture HTTP request data in JSON
                        insert_dict = OrderedDict( json.loads( request.data ) )

                        # Perform checks on dict describing values to be inserted
                        inputs_check = check_database_inputs( insert_dict, self.table )
                        if inputs_check:
                            return 'Error: ' + inputs_check

                        # Execute and commit SQL command
                        sql ='INSERT INTO ' + self.resource + '\n(' + ', '.join(insert_dict.keys()) + ')\nVALUES\n(' + \
                            ', '.join( ['%(' + x + ')s' for x in insert_dict.keys()] )  + ');'
                        self.cursor.execute( sql, insert_dict )
                        self.connection.commit()

                        return 'Successfully created resource with following SQL command:\n' + sql % insert_dict, 201

                    except Exception as e:
                        return 'Unsuccessful. Error:\n' + str(e)

                self.post = post_resource

    # Test of views creator

    members_views = ViewSet( server, pgconn, pgcurs, '/bentest/api/v1/members', members_table )

#    @server.route('/bentest/api/v1/members/<int:id>', methods = ['GET','PUT','DELETE'])
#    def members(id):
#
#        # GET method will return the JSON for the member with that ID
#        if request.method == 'GET':
#            try:
#                pgcurs.execute('SELECT * FROM members WHERE id = %d' % id)
#                values = pgcurs.fetchone()
#
#                if not values:
#                    return 'Unsuccessful. No member with id %d found.' % id
#
#                return jsonify(OrderedDict(zip(members_cols,values)))
#
#            except Exception as e:
#                return 'Unsuccessful. Error:\n' + str(e)
#
#        # PUT method will update the members table with the new, supplied JSON for the member with that ID
#        elif request.method == 'PUT':
#            try:
#                # Capture HTTP request data (JSON) and load into an update dictionary
#                update_dict = OrderedDict(json.loads(request.data))
#
#                # Ensure that the id matches
#                if id != int(update_dict['id']):
#                    return 'Error: ID does not match in body and URL'
#
#                # Perform checks on dict describing values to be updated
#                inputs_check = check_database_inputs(update_dict, members_table)
#                if inputs_check:
#                    return 'Error: ' + inputs_check
#
#                # Execute and commit SQL command
#                sql = 'UPDATE members\nSET\n' + ',\n'.join([x + ' = %(' + x + ')s' for x in update_dict.keys()]) + '\nWHERE id = %(id)s;'
#                pgcurs.execute( sql, update_dict )
#                pgconn.commit()
#
#                return 'Successfully updated member with following SQL command:\n' + sql % update_dict, 201
#
#            except Exception as e:
#                return 'Unsuccessful. Error:\n' + str(e)
#
#        # DELETE method will delete a row in the members table at the provided id
#        elif request.method == 'DELETE':
#
#            pgcurs.execute('DELETE FROM members WHERE id = %d' % id)
#
#            return 'Successfully deleted member with id %d' % id
#        
#    @server.route('/bentest/api/v1/members', methods = ['POST'])
#    def members_post():
#
#        # POST method will insert a row into the members table of the database with the new, supplied JSON
#        try:
#            # Capture HTTP request data in JSON
#            insert_dict = OrderedDict(json.loads(request.data))
#
#            # Perform checks on dict describing values to be inserted
#            inputs_check = check_database_inputs(insert_dict, members_table)
#            if inputs_check:
#                return 'Error: ' + inputs_check
#
#            # Execute and commit SQL command
#            sql ='INSERT INTO members\n(' + ', '.join(insert_dict.keys()) + ')\nVALUES\n(' + \
#                ', '.join( ['%(' + x + ')s' for x in insert_dict.keys()] )  + ');'
#            pgcurs.execute(sql, insert_dict)
#            pgconn.commit()
#
#            return 'Successfully created member with following SQL command:\n' + sql % insert_dict, 201
#
#        except Exception as e:
#            return 'Unsuccessful. Error:\n' + str(e)

    @server.route('/bentest/api/v1/projects/<int:id>', methods = ['GET','PUT','DELETE'])
    def projects(id):

        # GET method will return the JSON for the project with that ID
        if request.method == 'GET':
            try:
                pgcurs.execute('SELECT * FROM projects WHERE id = %d' % id)
                values = pgcurs.fetchone()

                if not values:
                    return 'Unsuccessful. No project with id %d found.' % id

                return jsonify(OrderedDict(zip(projects_cols,values)))

            except Exception as e:
                return 'Unsuccessful. Error:\n' + str(e)

        # PUT method will update the projects table with the new, supplied JSON for the project with that ID
        elif request.method == 'PUT':
            try:
                # Capture HTTP request data (JSON) and load into an update dictionary
                update_dict = OrderedDict(json.loads(request.data))

                # Ensure that the id matches
                if id != int(update_dict['id']):
                    return 'Error: ID does not match in body and URL'

                # Perform checks on dict describing values to be updated
                inputs_check = check_database_inputs(update_dict, projects_table)
                if inputs_check:
                    return 'Error: ' + inputs_check

                # Execute and commit SQL command
                sql = 'UPDATE projects\nSET\n' + ',\n'.join([x + ' = %(' + x + ')s' for x in update_dict.keys()]) + '\nWHERE id = %(id)s;'
                pgcurs.execute( sql, update_dict )
                pgconn.commit()

                return 'Successfully updated project with following SQL command:\n' + sql % update_dict, 201

            except Exception as e:
                return 'Unsuccessful. Error:\n' + str(e)

        # DELETE method will delete a row in the projects table at the provided id
        elif request.method == 'DELETE':

            pgcurs.execute('DELETE FROM projects WHERE id = %d' % id)

            return 'Successfully deleted projects with id %d' % id

    @server.route('/bentest/api/v1/projects', methods = ['POST'])
    def projects_post():

        # POST method will insert a row into the projects table of the database with the new, supplied JSON
        try:
            # Capture HTTP request data in JSON
            insert_dict = OrderedDict(json.loads(request.data))

            # Perform checks on dict describing values to be inserted
            inputs_check = check_database_inputs(insert_dict, projects_table)
            if inputs_check:
                return 'Error: ' + inputs_check

            # Execute and commit SQL command
            sql ='INSERT INTO projects\n(' + ', '.join(insert_dict.keys()) + ')\nVALUES\n(' + \
                ', '.join( ['%(' + x + ')s' for x in insert_dict.keys()] )  + ');'
            pgcurs.execute(sql, insert_dict)
            pgconn.commit()

            return 'Successfully created project with following SQL command:\n' + sql % insert_dict, 201

        except Exception as e:
            return 'Unsuccessful. Error:\n' + str(e)

    # Run the server on port 7000
    server.run('0.0.0.0',port=7000, debug=True)

main()

