# -*- coding: utf8 -*-

import re
import subprocess
import datetime
import json
from bs4 import BeautifulSoup
from django.http import HttpResponse
from django.shortcuts import render
from django.shortcuts import redirect
from data_center import models


def show_all(request, eg_id=None, ea_id=None, pa_id=None):
    if eg_id is None:
        subject = 'election-group'
    elif ea_id is None:
        subject = 'election-activity'
    elif pa_id is None:
        subject = 'candidate'
    else:
        subject = 'promise'

    title = _get_show_title(subject, eg_id, ea_id, pa_id)
    prefix = _get_show_prefix(subject, eg_id, ea_id, pa_id)
    buttons = _get_show_buttons(subject, eg_id, ea_id, pa_id)
    inputs = _get_show_inputs(subject, request.path, request.session, eg_id, ea_id, pa_id)

    args = {
        'title': title,
        'prefix': prefix,
        'buttons': buttons,
        'inputs': inputs,
    }

    return render(request, 'data-center-show.html', args)


def show_promise(request, eg_id, ea_id, pa_id, pr_id):
    promise = models.Promise.objects.get(id=pr_id)
    promise_info = {
        'id': promise.id,
        'content': promise.content,
    }

    subject = 'tag'
    prefix = _get_show_prefix(subject, eg_id, ea_id, pa_id)

    positive_tags_info = []
    negative_tags_info = []
    tags = models.Tag.objects.all()
    positive_has_tags = models.HasTag.objects.filter(promise=promise)
    positive_tag_ids = [has_tag.tag.id for has_tag in positive_has_tags]
    for tag in tags:
        tag_info = {
            'id': tag.id,
            'name': tag.name,
        }
        if tag.id in positive_tag_ids:
            positive_tags_info.append(tag_info)
        else:
            negative_tags_info.append(tag_info)

    all_tags_info = {
        'positive': positive_tags_info,
        'negative': negative_tags_info,
    }

    args = {
        'title': promise.brief,
        'prefix': prefix,
        'subject': subject,
        'promise': promise_info,
        'redirect': request.path,
        'tags': all_tags_info,
    }

    return render(request, 'data-center-promise.html', args)


def insert_all(request):
    if request.method != 'POST':
        return redirect('/data/')

    redirect_path = request.POST['redirect']
    subject = request.POST['subject']

    if subject == 'election-group':
        election_group_name = request.POST['name']
        election_group_nickname = request.POST['nickname']
        cec_url = request.POST['cec-url']

        cmd = ['wget', '-q', '-O', '-', cec_url]
        popen = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        webpage, trash = popen.communicate()
        soup = BeautifulSoup(webpage)

        date_div = soup.find('div', attrs={'class': 'date'})
        date_str = date_div.string
        mo = re.match(u'投票日期：中華民國(\d\d)年(\d\d)月(\d\d)日', date_str)
        yy, mm, dd = mo.group(1), mo.group(2), mo.group(3)
        yyyy, mm, dd = int(yy) + 1911, int(mm), int(dd)
        date = datetime.date(yyyy, mm, dd)

        try:
            election_group = models.ElectionGroup.objects.get(name=election_group_name)
        except models.ElectionGroup.DoesNotExist:
            election_group = models.ElectionGroup(name=election_group_name, nickname=election_group_nickname, vote_date=date)
            election_group.save()

        table = soup.find('table', attrs={'class': 'ctks'})
        rows = table.find_all('tr', attrs={'class': 'data'})

        for row in rows:
            cells = row.find_all('td')
            if 'rowspan' in cells[0].attrs:
                district_name = _format_district(cells.pop(0).string)
                try:
                    district = models.District.objects.get(name=district_name)
                except models.District.DoesNotExist:
                    district = models.District(name=district_name)
                    district.save()

                target = _find_target(election_group_name, district_name)

                try:
                    election_activity = models.ElectionActivity.objects.get(
                            election_group=election_group,
                            district=district,
                            target=target)
                except models.ElectionActivity.DoesNotExist:
                    election_activity = models.ElectionActivity(
                            election_group=election_group,
                            district=district,
                            target=target)
                    election_activity.save()

            name = cells[0].string.encode('utf8')
            party = cells[4].string.encode('utf8')
            elected = cells[7].string == '*'

            if elected:
                try:
                    candidate = models.Candidate.objects.get(name=name)
                except models.Candidate.DoesNotExist:
                    candidate = models.Candidate(name=name, party=party)
                    try:
                        candidate.save()
                    except:
                        candidate.name = name[4:]
                        candidate.save()
                except models.Candidate.MultipleObjectsReturned:
                    return render(request, 'data-center-error.html', {'message': '目前不支援同名同姓的狀況…'})

                try:
                    participation = models.Participation.objects.get(
                            candidate=candidate,
                            election_activity=election_activity,
                            result=models.Participation.ELECTED)
                except models.Participation.DoesNotExist:
                    participation = models.Participation(
                            candidate=candidate,
                            election_activity=election_activity,
                            result=models.Participation.ELECTED)
                    participation.save()

    elif subject == 'election-activity':
        election_group_id = request.POST['election-group-id']
        district_name = request.POST['district-name']
        election_activity_target = request.POST['target']

        election_group = models.ElectionGroup.objects.get(id=election_group_id)

        try:
            district = models.District.objects.get(name=district_name)
        except models.District.DoesNotExist:
            district = models.District(name=district_name)
            district.save()

        try:
            election_activity = models.ElectionActivity.objects.get(
                    election_group=election_group,
                    district=district,
                    target=election_activity_target)
            return render(request, 'data-center-error.html', {'message': '這個選舉已經存在啦!'})
        except models.ElectionActivity.DoesNotExist:
            election_activity = models.ElectionActivity(
                    election_group=election_group,
                    district=district,
                    target=election_activity_target)
            election_activity.save()

    elif subject == 'candidate':
        election_activity_id = request.POST['election-activity-id']
        candidate_name = request.POST['name'].strip()
        candidate_party = request.POST['party'].strip()
        participation_result = request.POST['result'].strip()

        if candidate_name == '' or candidate_party == '' or participation_result == '':
            return render(request, 'data-center-error.html', {'message': '候選人資料不可以是空白!'})
        elif participation_result != 'tbd' and participation_result != models.Participation.ELECTED:
            return render(request, 'data-center-error.html', {'message': '投票結果只能是 tbd 或是 elected!'})

        election_activity = models.ElectionActivity.objects.get(id=election_activity_id)

        try:
            candidate = models.Candidate.objects.get(name=candidate_name)
        except models.Candidate.DoesNotExist:
            candidate = models.Candidate(name=candidate_name, party=candidate_party)
            candidate.save()

        try:
            participation = models.Participation.objects.get(candidate=candidate, election_activity=election_activity)
            return render(request, 'data-center-error.html', {'message': '這個候選人已經在這次選舉裡啦!'})
        except models.Participation.DoesNotExist:
            participation = models.Participation(candidate=candidate,
                    election_activity=election_activity,
                    result=participation_result)
            participation.save()
    elif subject == 'promise':
        participation_id = request.POST['participation-id']
        promise_brief = request.POST['brief'].strip()
        promise_content = request.POST['content'].strip()

        if promise_brief == '' or promise_content == '':
            return render(request, 'data-center-error.html', {'message': '政見不可以是空白!'})

        participation = models.Participation.objects.get(id=participation_id)

        promise = models.Promise(participation=participation, brief=promise_brief, content=promise_content)
        promise.save()
    elif subject == 'tag':
        promise_id = request.POST['promise-id']
        promise = models.Promise.objects.get(id=promise_id)

        action = request.POST['action']
        if action == 'delete-exist' or action == 'add-exist':
            tag_id = request.POST['tag-id']
            tag = models.Tag.objects.get(id=tag_id)
        elif action == 'add-new':
            tag_name = request.POST['tag-name'].strip()
            try:
                tag = models.Tag.objects.get(name=tag_name)
            except models.Tag.DoesNotExist:
                tag = models.Tag(name=tag_name)
                tag.save()
        else:
            raise Exception('Unsupported tag action')

        if action == 'delete-exist':
            try:
                has_tag = models.HasTag.objects.get(tag=tag, promise=promise)
                has_tag.delete()
            except models.HasTag.DoesNotExist:
                pass
        elif action == 'add-exist' or action == 'add-new':
            try:
                has_tag = models.HasTag.objects.get(tag=tag, promise=promise)
            except models.HasTag.DoesNotExist:
                has_tag = models.HasTag(tag=tag, promise=promise)
                has_tag.save()
        else:
            raise Exception('Unsupported tag action')
    else:
        raise Exception('Unsupported subject')

    request.session['history'] = {}
    history_on = False
    if history_on:
        request.session['history'][subject] = {}
        for key, value in request.POST.items():
            request.session['history'][subject][key] = value

    return redirect(redirect_path)


def show_tmp(request):
    participations = models.Participation.objects.filter(election_activity__election_group__id=1)
    items = []
    for participation in participations:
        for category in ['學歷', '經歷']:
            for idx in range(3):
                item = {
                    'content': ','.join([participation.candidate.name.encode('utf8'), category, '', '', '']),
                }
                items.append(item)
    args = {
        'title': '候選人學經歷空白資料',
        'items': items,
    }

    return render(request, 'data-center-tmp.html', args)


def show_elected(request):
    election_activities = models.ElectionActivity.objects.filter(election_group__id=1)
    candidate_info_list = []
    for election_activity in election_activities:
        participations = models.Participation.objects.filter(election_activity=election_activity)
        for participation in participations:
            candidate = participation.candidate
            old_records = models.Participation.objects. \
                    filter(candidate=candidate, result=models.Participation.ELECTED). \
                    order_by('-election_activity__election_group__vote_date')
            if not old_records:
                continue

            candidate_info = {
                'name': candidate.name,
                'district': participation.election_activity.district.name.encode('utf8'),
                'records': [],
            }
            for old_record in old_records:
                group_str = str(old_record.election_activity.election_group)
                activity_str = str(old_record.election_activity)
                group_id = old_record.election_activity.election_group.id
                activity_id = old_record.election_activity.id
                participation_id = old_record.id
                promises = models.Promise.objects.filter(participation=old_record)
                num_promises = ' (已輸入 {} 條政見)'.format(promises.count()) if promises else ''
                references = models.Reference.objects.filter(participation=old_record)
                star = '' if references else '*'
                record_info = {
                    'content': star + group_str + ' - ' + activity_str + num_promises,
                    'link': '/data/{}/{}/{}'.format(group_id, activity_id, participation_id),
                }
                candidate_info['records'].append(record_info)
            candidate_info_list.append(candidate_info)

    args = {
        'candidates': candidate_info_list,
    }

    return render(request, 'data-center-elected.html', args)


def _format_district(district):
    mo = re.match(u'^(.{2}(市|縣))選(舉?)區$', district)
    if mo:
        return mo.group(1)

    mo = re.match(u'^(.{2}(市|縣))$', district)
    if mo:
        return mo.group(1)

    mo = re.match(u'^(.{2}(市|縣))第(\d+)選(舉?)區$', district)
    if mo:
        number = mo.group(3)
        return mo.group(1) + u'第 ' + str(int(number)) + u' 選舉區'

    mo = re.match(u'^(.{2}(市|縣))第(.+)選(舉?)區$', district)
    if mo:
        number = mo.group(3)
        return mo.group(1) + u'第 ' + str(_zh2num(number)) + u' 選舉區'

    raise Exception('Malformed election district')


def _zh2num(zh):
    table = {
        u'一': 1,
        u'二': 2,
        u'三': 3,
        u'四': 4,
        u'五': 5,
        u'六': 6,
        u'七': 7,
        u'八': 8,
        u'九': 9,
        u'十': 10,
        u'十一': 11,
        u'十二': 12,
        u'十三': 13,
        u'十四': 14,
        u'十五': 15,
        u'十六': 16,
        u'十七': 17,
        u'十八': 18,
        u'十九': 19,
        u'二十': 20,
    }

    if zh in table:
        return table[zh]

    raise Exception('Unsupported zh number')


def _find_target(election_group_name, district_name):
    if '立法委員' in election_group_name.encode('utf8'):
        return '立法委員'
    elif '縣市長' in election_group_name.encode('utf8'):
        if re.match(u'.{2}市', district_name):
            return '市長'
        elif re.match(u'.{2}縣', district_name):
            return '縣長'
    elif '縣市議員' in election_group_name.encode('utf8'):
        if re.match(u'.{2}市', district_name):
            return '市議員'
        elif re.match(u'.{2}縣', district_name):
            return '縣議員'
    elif '省市議員' in election_group_name.encode('utf8'):
        if re.match(u'.{2}市', district_name):
            return '市議員'
        elif re.match(u'.{2}縣', district_name):
            return '省議員'
    elif '國民大會代表' in election_group_name.encode('utf8'):
        return '國民大會代表'

    raise Exception("Can't determine election target")


def _get_show_title(subject, eg_id, ea_id, pa_id):
    if subject == 'election-group':
        title = '所有的大選們'
    elif subject == 'election-activity':
        election_group = models.ElectionGroup.objects.get(id=eg_id)
        title = str(election_group)
    elif subject == 'candidate':
        election_activity = models.ElectionActivity.objects.get(id=ea_id)
        title = str(election_activity)
    elif subject == 'promise':
        participation = models.Participation.objects.get(id=pa_id)
        title = str(participation)
    else:
        raise

    return title


def _get_show_prefix(subject, eg_id, ea_id, pa_id):
    if subject == 'election-group':
        prefix = ''
    elif subject == 'election-activity':
        prefix = ''
    elif subject == 'candidate':
        election_group = models.ElectionGroup.objects.get(id=eg_id)
        prefix = str(election_group)
    elif subject == 'promise':
        election_group = models.ElectionGroup.objects.get(id=eg_id)
        election_activity = models.ElectionActivity.objects.get(id=ea_id)
        prefix = str(election_group) + ' - ' + str(election_activity)
    elif subject == 'tag':
        election_group = models.ElectionGroup.objects.get(id=eg_id)
        election_activity = models.ElectionActivity.objects.get(id=ea_id)
        participation = models.Participation.objects.get(id=pa_id)
        prefix = str(election_group) + ' - ' + str(election_activity) + ' - ' + str(participation)
    else:
        raise

    return prefix


def _get_show_buttons(subject, eg_id, ea_id, pa_id):
    if subject == 'election-group':
        election_groups = models.ElectionGroup.objects.all().order_by('-vote_date')
        items = election_groups
        levels = []
    elif subject == 'election-activity':
        election_activities = models.ElectionActivity.objects.filter(election_group__id=eg_id)
        items = election_activities
        levels = [eg_id]
    elif subject == 'candidate':
        participations = models.Participation.objects.filter(election_activity__id=ea_id)
        items = participations
        levels = [eg_id, ea_id]
    elif subject == 'promise':
        promises = models.Promise.objects.filter(participation__id=pa_id)
        items = promises
        levels = [eg_id, ea_id, pa_id]
    else:
        raise

    buttons = []
    for item in items:
        button = {
            'levels': '/'.join([str(num) for num in (levels + [item.id])]),
            'name': str(item),
        }
        buttons.append(button)

    return buttons


def _get_show_inputs(subject, path, session, eg_id, ea_id, pa_id):
    if subject == 'election-group':
        enabled = False
        target = '大選'
        links = []
        items = [
            {
                'explicit': True,
                'name': 'name',
                'title': '大選全名',
                'placeholder': '比較正式的名稱',
            },
            {
                'explicit': True,
                'name': 'nickname',
                'title': '大選暱稱',
                'placeholder': '口頭上會講的',
            },
            {
                'explicit': True,
                'name': 'cec-url',
                'title': '中選會資料庫網址',
                'placeholder': '請參考 db.cec.gov.tw',
            },
        ]
    elif subject == 'election-activity':
        enabled = False
        target = '地方選舉'
        links = []
        items = [
            {
                'explicit': False,
                'name': 'election-group-id',
                'value': eg_id,
            },
            {
                'explicit': True,
                'name': 'district-name',
                'title': '選區',
                'placeholder': '請填全稱',
            },
            {
                'explicit': True,
                'name': 'target',
                'title': '職位',
                'placeholder': '像是 "市長" 、 "縣長" 、 "立法委員" 等等',
            },
        ]
    elif subject == 'candidate':
        enabled = False
        target = '候選人'
        links = []
        items = [
            {
                'explicit': False,
                'name': 'election-activity-id',
                'value': ea_id,
            },
            {
                'explicit': True,
                'name': 'name',
                'title': '候選人名稱',
                'placeholder': '請填全名',
            },
            {
                'explicit': True,
                'name': 'party',
                'title': '候選人政黨',
                'placeholder': '請填全名',
            },
            {
                'explicit': True,
                'name': 'result',
                'title': '選舉結果',
                'placeholder': '請填 tbd 或是 elected',
            },
        ]
    elif subject == 'promise':
        enabled = True
        target = '政見'
        references = models.Reference.objects.filter(participation__id=pa_id)
        links = []
        for reference in references:
            link = {
                'display': '選舉公報',
                'url': reference.url,
            }
            links.append(link)
        items = [
            {
                'explicit': False,
                'name': 'participation-id',
                'value': pa_id,
            },
            {
                'explicit': True,
                'name': 'brief',
                'title': '簡要',
                'placeholder': '請填一句話就好',
            },
            {
                'explicit': True,
                'name': 'content',
                'title': '內容',
                'placeholder': '可以詳細一點',
                'textarea': True,
            },
        ]
    else:
        raise

    if 'history' in session and subject in session['history']:
        for item in items:
            name = item['name']
            if name in session['history'][subject]:
                item['history'] = session['history'][subject][name]

    inputs = {
        'enabled': enabled,
        'subject': subject,
        'redirect': path,
        'target': target,
        'links': links,
        'list': items,
    }

    return inputs

def api_elected(request):
    election_activities = models.ElectionActivity.objects.filter(election_group__id=1)
    candidate_info_list = []
    for election_activity in election_activities:
        participations = models.Participation.objects.filter(election_activity=election_activity)
        for participation in participations:
            candidate = participation.candidate
            old_records = models.Participation.objects. \
                    filter(candidate=candidate, result=models.Participation.ELECTED). \
                    order_by('-election_activity__election_group__vote_date')
            if not old_records:
                continue

            candidate_info = {
                'name': candidate.name,
                'district': participation.election_activity.district.name.encode('utf8'),
                'records': [],
            }
            for old_record in old_records:
                promises = models.Promise.objects.filter(participation=old_record)
                election_activity = old_record.election_activity
                election_group = election_activity.election_group
                record_info = {
                    'election-group': election_group.name,
                    'vote-date': str(election_group.vote_date),
                    'district': election_activity.district.name.encode('utf8'),
                    'target': election_activity.target.encode('utf8'),
                    'promises': [
                        {
                            'brief': promise.brief.encode('utf8'),
                            'content': promise.content.encode('utf8'),
                        }
                        for promise in promises
                    ],
                }
                candidate_info['records'].append(record_info)
            candidate_info_list.append(candidate_info)

    return HttpResponse(json.dumps(candidate_info_list), content_type='application/json')

def api_all(request):
    election_groups = models.ElectionGroup.objects.all()
    election_groups_info = []
    for election_group in election_groups:
        election_activities = models.ElectionActivity.objects.filter(election_group=election_group)
        election_activities_info = []
        for election_activity in election_activities:
            participations = models.Participation.objects.filter(election_activity=election_activity)
            participations_info = []
            for participation in participations:
                promises = models.Promise.objects.filter(participation=participation)
                promises_info = []
                for promise in promises:
                    promise_info = {
                        'brief': promise.brief.encode('utf8'),
                        'content': promise.content.encode('utf8'),
                    }
                    promises_info.append(promise_info)
                participation_info = {
                    'promises': promises_info,
                    'candidate': participation.candidate.name.encode('utf8'),
                    'result': participation.result.encode('utf8'),
                }
                participations_info.append(participation_info)
            election_activity_info = {
                'participations': participations_info,
                'district': election_activity.district.name.encode('utf8'),
                'target': election_activity.target.encode('utf8'),
            }
            election_activities_info.append(election_activity_info)
        election_group_info = {
            'election-activities': election_activities_info,
            'name': election_group.name.encode('utf8'),
            'vote-date': str(election_group.vote_date),
        }
        election_groups_info.append(election_group_info)
    return HttpResponse(json.dumps(election_groups_info), content_type='application/json')

