from flask import Response
from flask_admin import expose
from metabrainz.admin import AdminIndexView, AdminBaseView
from metabrainz.model.user import User, STATE_PENDING, STATE_ACTIVE, STATE_REJECTED, STATE_WAITING, STATE_LIMITED
from metabrainz.model.token import Token
from metabrainz.model.token_log import TokenLog
from metabrainz.model.access_log import AccessLog
from metabrainz import flash
from flask import request, redirect, url_for
import time
import json


class HomeView(AdminIndexView):

    @expose('/')
    def index(self):
        return self.render(
            'admin/home.html',
            pending_users=User.get_all(state=STATE_PENDING),
            waiting_users=User.get_all(state=STATE_WAITING),
        )


class UsersView(AdminBaseView):

    @expose('/')
    def index(self):
        value = request.args.get('value')
        results = User.search(value) if value else []
        return self.render('admin/users/index.html',
                           value=value, results=results)

    @expose('/<int:user_id>')
    def details(self, user_id):
        user = User.get(id=user_id)
        active_tokens = Token.get_all(owner_id=user.id, is_active=True)
        return self.render(
            'admin/users/details.html',
            user=user,
            active_tokens=active_tokens,
        )

    @expose('/<int:user_id>/stats')
    def details_stats(self, user_id):
        stats = AccessLog.get_hourly_usage(user_id=user_id)
        return Response(json.dumps([{'data': [[
                time.mktime(i[0].utctimetuple()) * 1000,
                i[1]
            ] for i in stats]}]),
            content_type='application/json; charset=utf-8')

    @expose('/approve')
    def approve(self):
        user_id = request.args.get('user_id')
        if request.args.get('limited'):
            User.get(id=user_id).set_state(STATE_LIMITED)
        else:
            User.get(id=user_id).set_state(STATE_ACTIVE)
        flash.info("User #%s has been approved." % user_id)

        # Redirecting to the next pending user
        next_user = User.get(state=STATE_PENDING)
        if next_user:
            return redirect(url_for('.details', user_id=next_user.id))
        else:
            flash.info("No more pending users.")
            return redirect(url_for('.index'))

    @expose('/reject')
    def reject(self):
        user_id = request.args.get('user_id')
        User.get(id=user_id).set_state(STATE_REJECTED)
        flash.warn("User #%s has been rejected." % user_id)

        # Redirecting to the next pending user
        next_user = User.get(state=STATE_PENDING)
        if next_user:
            return redirect(url_for('.details', user_id=next_user.id))
        else:
            flash.info("No more pending users.")
            return redirect(url_for('.index'))

    @expose('/wait')
    def wait(self):
        user_id = request.args.get('user_id')
        User.get(id=user_id).set_state(STATE_WAITING)
        flash.info("User #%s has been put into the waiting list." % user_id)

        # Redirecting to the next pending user
        next_user = User.get(state=STATE_PENDING)
        if next_user:
            return redirect(url_for('.details', user_id=next_user.id))
        else:
            flash.info("No more pending users.")
            return redirect(url_for('.index'))

    @expose('/revoke-token')
    def revoke_token(self):
        token_value = request.args.get('token_value')
        token = Token.get(value=token_value)
        token.revoke()
        flash.info("Token %s has been revoked." % token_value)
        return redirect(url_for('.details', user_id=token.owner_id))


class CommercialUsersView(AdminBaseView):

    @expose('/')
    def index(self):
        page = int(request.args.get('page', default=1))
        if page < 1:
            return redirect(url_for('.index'))
        limit = 20
        offset = (page - 1) * limit
        users, count = User.get_all_commercial(limit=limit, offset=offset)
        return self.render('admin/commercial-users/index.html', users=users,
                           page=page, limit=limit, count=count)


class TokensView(AdminBaseView):

    @expose('/')
    def index(self):
        value = request.args.get('value')
        results = Token.search_by_value(value) if value else []
        return self.render('admin/tokens/search.html',
                           value=value, results=results)


class StatsView(AdminBaseView):

    @expose('/')
    def overview(self):
        return self.render(
            'admin/stats/overview.html',
            active_user_count=AccessLog.active_user_count(),
            top_downloaders=AccessLog.top_downloaders(10),
            token_actions=TokenLog.list(10)[0],
        )

    @expose('/token-log')
    def token_log(self):
        page = int(request.args.get('page', default=1))
        if page < 1:
            return redirect(url_for('.token_log'))
        limit = 20
        offset = (page - 1) * limit
        token_actions, count = TokenLog.list(limit=limit, offset=offset)
        return self.render(
            'admin/stats/token-log.html',
            token_actions=token_actions,
            page=page,
            limit=limit,
            count=count,
        )

    @expose('/usage')
    def hourly_usage_data(self):
        stats = AccessLog.get_hourly_usage()
        return Response(json.dumps([{'data': [[
                time.mktime(i[0].utctimetuple()) * 1000,
                i[1]
            ] for i in stats]}]),
            content_type='application/json; charset=utf-8')
