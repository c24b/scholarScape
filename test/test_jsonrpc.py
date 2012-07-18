from bson.objectid import ObjectId
from scholarScape.server.rpc import scholarScape
from scholarScape.server.db_lib import Duplicates
from mock import patch
import pymongo
import uuid
import json
import pytest

@patch.object(Duplicates, "get_list_of_potential_duplicates")
@patch.object(Duplicates, "count_duplicates_left_for_cluster")
@patch.object(Duplicates, "count_already_checked")
@patch.object(Duplicates, "get_cluster_with_possible_duplicates_left")
class TestJsonRPCIsolation:
    def test_give_me_duplicates_no_cluster_id(self, get_cluster_with_possible_duplicates_left, count_already_checked, count_duplicates_left_for_cluster, get_list_of_potential_duplicates):
        expected = [{"test1" : 1},{"test2" : 2},{"test3" : 3}]

        get_cluster_with_possible_duplicates_left.return_value = 2
        count_already_checked.return_value = 352
        count_duplicates_left_for_cluster.return_value = 700
        get_list_of_potential_duplicates.return_value = expected

        jsonrpc = scholarScape(None)
        result = jsonrpc.jsonrpc_give_me_duplicates("project", "campaign", 3)

        assert result == {
            'number_of_duplicates_left_for_cluster' : 700,
            'number_duplicates_already_checked' : 352,
            'duplicates' : map(json.dumps, expected),
            'cluster' : 2,
            }

        get_cluster_with_possible_duplicates_left.assert_called_once_with(None, "project", "campaign")
        count_already_checked.assert_called_once_with(None, "project", "campaign")
        count_duplicates_left_for_cluster.assert_called_once_with(None, "project", "campaign", 2)
        get_list_of_potential_duplicates.assert_called_once_with(None, "project", "campaign", 2)

    def test_give_me_duplicates_with_cluster_id(self, get_cluster_with_possible_duplicates_left, count_already_checked, count_duplicates_left_for_cluster, get_list_of_potential_duplicates):
        expected = [{"test1" : 1},{"test2" : 2},{"test3" : 3}]

        get_cluster_with_possible_duplicates_left.return_value = 2
        count_already_checked.return_value = 352
        count_duplicates_left_for_cluster.return_value = 700
        get_list_of_potential_duplicates.return_value = expected

        jsonrpc = scholarScape(None)
        result = jsonrpc.jsonrpc_give_me_duplicates("project", "campaign", 3, 2)

        assert result == {
            'number_of_duplicates_left_for_cluster' : 700,
            'number_duplicates_already_checked' : 352,
            'duplicates' : map(json.dumps, expected),
            'cluster' : 2,
            }

        assert not get_cluster_with_possible_duplicates_left.called
        count_already_checked.assert_called_once_with(None, "project", "campaign")
        count_duplicates_left_for_cluster.assert_called_once_with(None, "project", "campaign", 2)
        get_list_of_potential_duplicates.assert_called_once_with(None, "project", "campaign", 2)

@pytest.mark.slow
class TestJsonRPCIntegration:
    def setup_class(self):
        self.connection = pymongo.Connection()
        self.database_name = str(uuid.uuid4())
        self.database = self.connection[self.database_name]
        self.jsonrpc = scholarScape(self.database)
        self.project = "test_project"
        self.campaign = "test_campaign"
        self.project_col = self.database[self.project]
        self.campaign_col = self.database["__dup__"+self.project+"-"+self.campaign]

    def teardown_method(self, method):
        self.project_col.remove()
        self.campaign_col.remove()

    def teardown_class(self):
        self.connection.drop_database(self.database)

    def test_duplicates(self):
        _id1 = ObjectId()
        _id2 = ObjectId()
        _id3 = ObjectId()
        self.project_col.insert({"_id" : _id1})
        self.project_col.insert({"_id" : _id2})
        self.project_col.insert({"_id" : _id3})
        self.campaign_col.insert({"_id1" : _id1, "_id2" : _id2})
        self.campaign_col.insert({"_id1" : _id2, "_id2" : _id3})
        self.jsonrpc.jsonrpc_duplicate_human_check(self.project, self.campaign, [str(_id1), str(_id2), str(_id3)], True)
        assert self.campaign_col.find({"human_say" : True}).count() == 2
        assert self.project_col.find_one({"type" : "super_publication"})

    def test_give_me_duplicates(self):
        _id1 = ObjectId()
        _id2 = ObjectId()
        _id3 = ObjectId()
        _id4 = ObjectId()
        _id5 = ObjectId()
        self.project_col.insert({"_id" : _id1, "title" : "test1"})
        self.project_col.insert({"_id" : _id2, "title" : "test2"})
        self.project_col.insert({"_id" : _id3, "title" : "test3"})
        self.project_col.insert({"_id" : _id4, "title" : "test4"})
        self.project_col.insert({"_id" : _id5, "title" : "test5"})
        self.campaign_col.insert({"_id1" : _id1, "_id2" : _id2, "cluster" : 1, "title_score" : 0.9})
        self.campaign_col.insert({"_id1" : _id2, "_id2" : _id3, "cluster" : 1, "title_score" : 0.9})
        self.campaign_col.insert({"_id1" : _id3, "_id2" : _id4, "cluster" : 2, "title_score" : 0.3})
        self.campaign_col.insert({"_id1" : _id4, "_id2" : _id5, "cluster" : 2, "title_score" : 0.9})

        duplicates = self.jsonrpc.jsonrpc_give_me_duplicates(self.project, self.campaign, 3, 1)
        assert len(duplicates["duplicates"]) == 3
        assert duplicates["cluster"] == 1
        for dup in duplicates["duplicates"]:
            dup = json.loads(dup)
            assert dup["title"] in ["test1", "test2", "test3"]

        duplicates = self.jsonrpc.jsonrpc_give_me_duplicates(self.project, self.campaign, 2, 1)
        assert len(duplicates["duplicates"]) == 2
        assert duplicates["cluster"] == 1
        for dup in duplicates["duplicates"]:
            dup = json.loads(dup)
            assert dup["title"] in ["test1", "test2", "test3"]

        duplicates = self.jsonrpc.jsonrpc_give_me_duplicates(self.project, self.campaign, 3, 2)
        assert len(duplicates["duplicates"]) == 2
        assert duplicates["cluster"] == 2
        for dup in duplicates["duplicates"]:
            dup = json.loads(dup)
            assert dup["title"] in ["test4", "test5"]

    def test_marked_as_not_duplicate(self):
        _id1 = ObjectId()
        _id2 = ObjectId()
        _id3 = ObjectId()
        self.project_col.insert({"_id" : _id1})
        self.project_col.insert({"_id" : _id2})
        self.project_col.insert({"_id" : _id3})
        self.campaign_col.insert({"_id1" : _id1, "_id2" : _id2})
        self.campaign_col.insert({"_id1" : _id2, "_id2" : _id3})
        self.jsonrpc.jsonrpc_duplicate_human_check(self.project, self.campaign, [str(_id1), str(_id2), str(_id3)], False)
        assert self.campaign_col.find({"human_say" : False}).count() == 2
        assert not self.project_col.find_one({"type" : "super_publication"})

    def test_marked_duplicates_dont_reappear(self):
        _id1 = ObjectId()
        _id2 = ObjectId()
        self.project_col.insert({"_id" : _id1, "title" : "test1"})
        self.project_col.insert({"_id" : _id2, "title" : "test2"})
        self.campaign_col.insert({"_id1" : _id1, "_id2" : _id2, "cluster" : 1, "title_score" : 0.9})

        duplicates = self.jsonrpc.jsonrpc_give_me_duplicates(self.project, self.campaign, 3, 1)
        assert len(duplicates["duplicates"]) == 2

        self.jsonrpc.jsonrpc_duplicate_human_check(self.project, self.campaign, [str(_id1), str(_id2)], True)

        duplicates = self.jsonrpc.jsonrpc_give_me_duplicates(self.project, self.campaign, 3, 1)
        assert len(duplicates["duplicates"]) == 0

    def test_marked_as_not_duplicate_dont_reappear(self):
        _id1 = ObjectId()
        _id2 = ObjectId()
        self.project_col.insert({"_id" : _id1, "title" : "test1"})
        self.project_col.insert({"_id" : _id2, "title" : "test2"})
        self.campaign_col.insert({"_id1" : _id1, "_id2" : _id2, "cluster" : 1, "title_score" : 0.9})

        duplicates = self.jsonrpc.jsonrpc_give_me_duplicates(self.project, self.campaign, 3, 1)
        assert len(duplicates["duplicates"]) == 2

        self.jsonrpc.jsonrpc_duplicate_human_check(self.project, self.campaign, [str(_id1), str(_id2)], False)

        duplicates = self.jsonrpc.jsonrpc_give_me_duplicates(self.project, self.campaign, 3, 1)
        assert len(duplicates["duplicates"]) == 0

    def test_giveme_duplicates_no_clusterid(self):
        _id1 = ObjectId()
        _id2 = ObjectId()
        _id3 = ObjectId()
        _id4 = ObjectId()

        duplicates = self.jsonrpc.jsonrpc_give_me_duplicates(self.project, self.campaign, 3)
        assert duplicates["cluster"] == -1
        assert duplicates["duplicates"] == []

        self.project_col.insert({"_id" : _id1, "title" : "test1"})
        self.project_col.insert({"_id" : _id2, "title" : "test2"})
        self.project_col.insert({"_id" : _id3, "title" : "test3"})
        self.project_col.insert({"_id" : _id4, "title" : "test4"})
        self.campaign_col.insert({"_id1" : _id1, "_id2" : _id2, "cluster" : 1, "title_score" : 0.9})
        self.campaign_col.insert({"_id1" : _id3, "_id2" : _id4, "cluster" : 2, "title_score" : 0.9})

        duplicates = self.jsonrpc.jsonrpc_give_me_duplicates(self.project, self.campaign, 3)
        assert duplicates["cluster"] in [1, 2]
        if duplicates["cluster"] == 1:
            self.jsonrpc.jsonrpc_duplicate_human_check(self.project, self.campaign, [str(_id1), str(_id2)], True)
            duplicates = self.jsonrpc.jsonrpc_give_me_duplicates(self.project, self.campaign, 3)
            assert duplicates["cluster"] == 2
            self.jsonrpc.jsonrpc_duplicate_human_check(self.project, self.campaign, [str(_id3), str(_id4)], True)
        else:
            self.jsonrpc.jsonrpc_duplicate_human_check(self.project, self.campaign, [str(_id3), str(_id4)], True)
            duplicates = self.jsonrpc.jsonrpc_give_me_duplicates(self.project, self.campaign, 3)
            self.jsonrpc.jsonrpc_duplicate_human_check(self.project, self.campaign, [str(_id1), str(_id2)], True)
            assert duplicates["cluster"] == 1

        duplicates = self.jsonrpc.jsonrpc_give_me_duplicates(self.project, self.campaign, 3)
        assert duplicates["cluster"] == -1
        assert duplicates["duplicates"] == []
