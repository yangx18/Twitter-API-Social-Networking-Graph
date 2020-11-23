import twitter
import json
import sys
import time
from urllib.error import URLError
from http.client import BadStatusLine
from functools import partial
from sys import maxsize as maxint
import networkx as nx



def oauth_login():

    '''
    Login function,
    with saving my CONSUMER_KEY, CONSUMER_SECRET, OAUTH_TOKEN, OAUTH_TOKEN_SECRET
    '''

    CONSUMER_KEY = 'YANG'
    CONSUMER_SECRET = 'XIAO'
    OAUTH_TOKEN = 'AKA'
    OAUTH_TOKEN_SECRET = 'BUG KILLER'

    auth = twitter.oauth.OAuth(OAUTH_TOKEN, OAUTH_TOKEN_SECRET,
                               CONSUMER_KEY, CONSUMER_SECRET)

    twitter_api = twitter.Twitter(auth=auth)
    return twitter_api

def make_twitter_request(twitter_api_func, max_errors=10, *args, **kw):

    '''
    make_twitter_request function from cookbook.
    # A nested helper function that handles common HTTPErrors. Return an updated
    # value for wait_period if the problem is a 500 level error. Block until the
    # rate limit is reset if it's a rate limiting issue (429 error). Returns None
    # for 401 and 404 errors, which requires special handling by the caller.
    '''

    def handle_twitter_http_error(e, wait_period=2, sleep_when_rate_limited=True):

        if wait_period > 3600: # Seconds
            print('Too many retries. Quitting.', file=sys.stderr)
            raise e

        if e.e.code == 401:
            print('Encountered 401 Error (Not Authorized)', file=sys.stderr)
            return None
        elif e.e.code == 404:
            print('Encountered 404 Error (Not Found)', file=sys.stderr)
            return None
        elif e.e.code == 429:
            print('Encountered 429 Error (Rate Limit Exceeded)', file=sys.stderr)
            if sleep_when_rate_limited:
                print("Retrying in 15 minutes...ZzZ...", file=sys.stderr)
                sys.stderr.flush()
                time.sleep(60*15)
                print('...ZzZ...Awake now and trying again.', file=sys.stderr)
                return 2
            else:
                raise e # Caller must handle the rate limiting issue
        elif e.e.code in (500, 502, 503, 504):
            print('Encountered {0} Error. Retrying in {1} seconds'\
                  .format(e.e.code, wait_period), file=sys.stderr)
            time.sleep(wait_period)
            wait_period *= 1.5
            return wait_period
        else:
            raise e

    # End of nested helper function

    wait_period = 2
    error_count = 0

    while True:
        try:
            return twitter_api_func(*args, **kw)
        except twitter.api.TwitterHTTPError as e:
            error_count = 0
            wait_period = handle_twitter_http_error(e, wait_period)
            if wait_period is None:
                return
        except URLError as e:
            error_count += 1
            time.sleep(wait_period)
            wait_period *= 1.5
            print("URLError encountered. Continuing.", file=sys.stderr)
            if error_count > max_errors:
                print("Too many consecutive errors...bailing out.", file=sys.stderr)
                raise
        except BadStatusLine as e:
            error_count += 1
            time.sleep(wait_period)
            wait_period *= 1.5
            print("BadStatusLine encountered. Continuing.", file=sys.stderr)
            if error_count > max_errors:
                print("Too many consecutive errors...bailing out.", file=sys.stderr)
                raise

def get_user_profile(twitter_api, screen_names=None, user_ids=None):

    '''
    get_user_profile function from cookbook,
    help developer to get server users's information by user_ids or screen_names
    '''

    # Must have either screen_name or user_id (logical xor)
    assert (screen_names != None) != (user_ids != None), \
    "Must have screen_names or user_ids, but not both"

    items_to_info = {}

    items = screen_names or user_ids

    while len(items) > 0:

        # Process 100 items at a time per the API specifications for /users/lookup.
        # See http://bit.ly/2Gcjfzr for details.

        items_str = ','.join([str(item) for item in items[:100]])
        items = items[100:]

        if screen_names:
            response = make_twitter_request(twitter_api.users.lookup,
                                            screen_name=items_str)
        else: # user_ids
            response = make_twitter_request(twitter_api.users.lookup,
                                            user_id=items_str)

        for user_info in response:
            if screen_names:
                items_to_info[user_info['screen_name']] = user_info
            else: # user_ids
                items_to_info[user_info['id']] = user_info

    return items_to_info

def get_friends_followers_ids(twitter_api, screen_name=None, user_id=None,
                              friends_limit=maxint, followers_limit=maxint):

    '''
    get_friends_followers_ids function from cookbook,
    which help developer get target person's friends and followers,
    by giving his/her screen_name or user_id.
    '''

    # Must have either screen_name or user_id (logical xor)
    assert (screen_name != None) != (user_id != None), \
    "Must have screen_name or user_id, but not both"

    # See http://bit.ly/2GcjKJP and http://bit.ly/2rFz90N for details
    # on API parameters

    get_friends_ids = partial(make_twitter_request, twitter_api.friends.ids,
                              count=5000)
    get_followers_ids = partial(make_twitter_request, twitter_api.followers.ids,
                                count=5000)

    friends_ids, followers_ids = [], []

    for twitter_api_func, limit, ids, label in [
                    [get_friends_ids, friends_limit, friends_ids, "friends"],
                    [get_followers_ids, followers_limit, followers_ids, "followers"]
                ]:

        if limit == 0: continue

        cursor = -1
        while cursor != 0:

            # Use make_twitter_request via the partially bound callable...
            if screen_name:
                response = twitter_api_func(screen_name=screen_name, cursor=cursor)
            else: # user_id
                response = twitter_api_func(user_id=user_id, cursor=cursor)

            if response is not None:
                ids += response['ids']
                cursor = response['next_cursor']
            if not screen_name:
                print('Fetched {0} total {1} ids for {2}, who {3}'.format(len(ids),\
                      label, user_id, twitter_api.users.show(user_id=user_id)['screen_name'] ),file=sys.stderr)
            print('Fetched {0} total {1} ids for {2}'.format(len(ids),\
                  label, (user_id or screen_name)),file=sys.stderr)

            # XXX: You may want to store data during each iteration to provide an
            # an additional layer of protection from exceptional circumstances

            if len(ids) >= limit or response is None:
                break

    # Do something useful with the IDs, like store them to disk...
    return friends_ids[:friends_limit], followers_ids[:followers_limit]


def findfivefri(twitter_api, friends_ids, follower_ids):

    '''
    My own function.
    I create this findfivefri function to help developer find target person's reciprocal_friends,
    and return the 5 most popular reciprocal_friends.

    # def a function to look for 5 most pupolar common friends
    # return 5 reciprocal_friends with largest followers count
    '''

    # Using set to get reciprocal_friends between firends and followers
    reciprocal_friends = set(friends_ids)&set(follower_ids)

    # Using get_user_profile function to return the deteil info from reciprocal friends
    friends_profile = get_user_profile(twitter_api,
                                        user_ids=list(reciprocal_friends))

    five_popular_friends_ids=[]
    popular_friends = {}

    #  Save each reciprocal friend's id as key, and his/her followers_count num as value
    for k,v in friends_profile.items():
        popular_friends[k] = int(v['followers_count'])

    #sorted these reciprocal firends by Descending, and assign the highest 5 into five_popular_friends_ids
    five_popular_friends_ids = sorted(popular_friends,
                                        key=popular_friends.get,reverse=True)[:5]

    # return 5 popular friends
    return five_popular_friends_ids

def crawl_followers(twitter_api, screen_name, Graph, limit=5000, depth=2, **mongo_conn_kw):

    '''
    I create this crawl_followers function by modifing instructor's Simplified Version of crawler using make_twitter_request.
    Recive twitter_api, screen_name, and max_depth.
    return the network graph within max_depth by using break-first-search
    Each layer(depth), I call findfivefri fucntion to get the most popular 5 reciprocal friends,
    until 100 users/nodes or finish the 4th distance.
    '''
    reciprocal_friends_dict= {}

    seed_id = str(twitter_api.users.show(screen_name=screen_name)['id'])

    # Using get_friends_ids function to get target's friends_ids, and followers by user_id
    friends_ids, follower_ids = get_friends_followers_ids(twitter_api, user_id=seed_id,
                                              friends_limit=limit, followers_limit=limit)

    # Calling findfivefri fucntion to get most popular 5 reciprocal friends
    five_popular_friends_ids = findfivefri(twitter_api, friends_ids, follower_ids)
    print(' distance-1 friends: ', five_popular_friends_ids, screen_name)

    reciprocal_friends_dict["distance-1 friends"] = five_popular_friends_ids

    # queue of 5 friends for BFS
    next_queue = five_popular_friends_ids

    #Create a social network edges based on the results of 5 most popular firends by using networkx package
    G.add_edges_from([(int(seed_id),recip_fri) for recip_fri in five_popular_friends_ids])

    #record all of the reciprocal friends
    ids = next_queue
    d = 1 # depth

    #BFS
    while d < depth:
        d += 1
        (queue, next_queue) = (next_queue, [])

        for fid in queue:

            # Using get_friends_ids function to get target's friends_ids, and followers by user_id
            friends_ids, follower_ids = get_friends_followers_ids(twitter_api, user_id=fid,
                                                     friends_limit=limit,
                                                     followers_limit=limit)
            # Calling findfivefri fucntion to get most popular 5 reciprocal friends
            five_popular_friends_ids = findfivefri(twitter_api, friends_ids, follower_ids)

            #Pruning, only add friends first time show up.
            if five_popular_friends_ids:
                for i in five_popular_friends_ids:
                    if i not in next_queue and i not in ids:
                        next_queue.append(i)

                        #Create a social network edges based on the results between friends and his/her reciprocal_friends
                        G.add_edge(fid,i)

            else: print(str(fid)+' is protected')

        print(' distance-{0} friends: {1} '.format(d,next_queue))
        ids += next_queue

        dis_str = 'distance-'+str(d) +'friends'
        reciprocal_friends_dict[dis_str] = next_queue



        # gather at least 100 users/nodes, then break
        if len(ids) >= 100: break

    #return gathered at least 100 users/nodes for your social network, and Graph G
    return ids,reciprocal_friends_dict, G


# networkx return diameter and averge distance
def eccentricity(G, v=None, sp=None):

    '''
    Provided by Networkx
    Returns the eccentricity of nodes in G.
    The eccentricity of a node v is the maximum distance from v to
    all other nodes in G.
    '''
    order = G.order()

    e = {}
    for n in G.nbunch_iter(v):
        if sp is None:
            length = nx.single_source_shortest_path_length(G, n)
            L = len(length)
        else:
            try:
                length = sp[n]
                L = len(length)
            except TypeError as e:
                raise nx.NetworkXError('Format of "sp" is invalid.') from e
        if L != order:
            if G.is_directed():
                msg = (
                    "Found infinite path length because the digraph is not"
                    " strongly connected"
                )
            else:
                msg = "Found infinite path length because the graph is not" " connected"
            raise nx.NetworkXError(msg)

        e[n] = max(length.values())

    if v in G:
        return e[v]  # return single value
    else:
        return e

def diameter(G, e=None, usebounds=False):

    '''
    Provided by Networkx

    # Return Diameter
    '''

    if usebounds is True and e is None and not G.is_directed():
        return extrema_bounding(G, compute="diameter")
    if e is None:
        e = eccentricity(G)
    return max(e.values())

def average_shortest_path_length(G, weight=None, method=None):

    '''
    Provided by Networkx

    #return average Distance
    '''

    single_source_methods = ["unweighted", "dijkstra", "bellman-ford"]
    all_pairs_methods = ["floyd-warshall", "floyd-warshall-numpy"]
    supported_methods = single_source_methods + all_pairs_methods

    if method is None:
        method = "unweighted" if weight is None else "dijkstra"
    if method not in supported_methods:
        raise ValueError(f"method not supported: {method}")

    n = len(G)
    # For the special case of the null graph, raise an exception, since
    # there are no paths in the null graph.
    if n == 0:
        msg = (
            "the null graph has no paths, thus there is no average"
            "shortest path length"
        )
        raise nx.NetworkXPointlessConcept(msg)
    # For the special case of the trivial graph, return zero immediately.
    if n == 1:
        return 0
    # Shortest path length is undefined if the graph is disconnected.
    if G.is_directed() and not nx.is_weakly_connected(G):
        raise nx.NetworkXError("Graph is not weakly connected.")
    if not G.is_directed() and not nx.is_connected(G):
        raise nx.NetworkXError("Graph is not connected.")

    # Compute all-pairs shortest paths.
    def path_length(v):
        if method == "unweighted":
            return nx.single_source_shortest_path_length(G, v)
        elif method == "dijkstra":
            return nx.single_source_dijkstra_path_length(G, v, weight=weight)
        elif method == "bellman-ford":
            return nx.single_source_bellman_ford_path_length(G, v, weight=weight)

    if method in single_source_methods:
        # Sum the distances for each (ordered) pair of source and target node.
        s = sum(l for u in G for l in path_length(u).values())
    else:
        if method == "floyd-warshall":
            all_pairs = nx.floyd_warshall(G, weight=weight)
            s = sum([sum(t.values()) for t in all_pairs.values()])
        elif method == "floyd-warshall-numpy":
            s = nx.floyd_warshall_numpy(G, weight=weight).sum()
    return s / (n * (n - 1))


#Main Fucntion Enter
'''
Author: Yang Xiao 
'''
if __name__ == '__main__':

    #login
    twitter_api = oauth_login()
    print('login:',twitter_api)

    #screen_name start point
    screen_name = 'RealTrump '
    G = nx.Graph()


    #Retrieve his/her reciprocal_friends witch the most popular fives by n th depth
    n = input('Retrieve his/her reciprocal_friends witch the most popular fives by n th depth:\n')
    n = int(n)
    reciprocal_friends, reciprocal_friends_dict,  G = crawl_followers(twitter_api, screen_name, Graph=G, depth = n)

    print('-------------1----------------')
    print(reciprocal_friends)

    print('-------------2----------------')
    print("Number of Nodes ={0}.".format(G.number_of_nodes()))
    print("Number of Edges ={0}.".format(G.number_of_edges()))
    print("Node list = ", G.nodes())
    print("Edge list = ", G.edges())

    print('-------------3----------------')
    print("Diameter = ",diameter(G))
    print("Averge Distance: ",average_shortest_path_length(G))



    network_dict = {"number_of_nodesof nodes":G.number_of_nodes(), "number_of_edges":G.number_of_edges(), "node_list":list(G.nodes()), "edge_list":list(G.edges()),
                    "diameter":diameter(G), "average_distance":average_shortest_path_length(G)}

    #Saving these to local file
    with open("socialnetwork.json",'w')as f:
        json.dump(reciprocal_friends_dict,f)
        print('saved...reciprocal_friends')
    f.close()

    with open("network.json",'w')as fn:
        json.dump(network_dict,fn)
        print('saved...network_dict')
    fn.close()
