from django.conf.urls import patterns, url

urlpatterns = patterns('',
    url(r'^elected/$', 'data_center.views.show_elected'),

    url(r'^insert/$', 'data_center.views.insert_all'),

    url(r'^tmp/$', 'data_center.views.show_tmp'),

    url(r'^api/elected/$', 'data_center.views.api_elected'),
    url(r'^api/all/$', 'data_center.views.api_all'),
    url(r'^api/front-end/map/(?P<target>.+)/$', 'data_center.views.api_map'),
    url(r'^api/front-end/info/(?P<target>.+)/$', 'data_center.views.api_info'),

    url(r'^$', 'data_center.views.show_all'),
    url(r'^(?P<eg_id>\d+)/$', 'data_center.views.show_all'),
    url(r'^(?P<eg_id>\d+)/(?P<ea_id>\d+)/$', 'data_center.views.show_all'),
    url(r'^(?P<eg_id>\d+)/(?P<ea_id>\d+)/(?P<pa_id>\d+)/$', 'data_center.views.show_all'),
    url(r'^(?P<eg_id>\d+)/(?P<ea_id>\d+)/(?P<pa_id>\d+)/(?P<pr_id>\d+)/$', 'data_center.views.show_promise'),
)
