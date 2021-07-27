import datetime

from dds.consts import DECIMALS
from dds.utilities import get_media_if_exists
from django.db.models import Q
from django.shortcuts import render
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import BidsHistory, ListingHistory, TokenHistory, UserAction
from .utils import quick_sort


class GetActivityView(APIView):
    '''
    View for activity page
    '''

    @swagger_auto_schema(
        operation_description="get activity",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'address': openapi.Schema(type=openapi.TYPE_STRING)
            }
        )
    )
    def post(self, request, page):

        address = request.data.get('address')
        if request.query_params:
            query = request.query_params['type']
        else:
            query = None

        start = (page - 1) * 50
        end = page * 50

        diff_activity = []
        print(address) 
        if query:
            print('query:', query)
            if 'purchase' in query or 'sale' in query:
                print('sale!')
                if address:
                    buy  = TokenHistory.objects.filter(
                        Q(new_owner__username=address) | Q(old_owner__username=address),
                        method='Buy', 
                    ).order_by('-date')[start:end]
                else:
                    buy  = TokenHistory.objects.filter(method='Buy').order_by('-date')[start:end]
                for item in buy:
                    diff_activity.append(item)
            
            if 'transfer' in query:
                print('transter!')
                if address:
                    transfer = TokenHistory.objects.filter(
                        Q(new_owner__username=address) | Q(old_owner__username=address),
                        method='Transfer', 
                    ).order_by('-date')[start:end]
                else:
                    transfer = TokenHistory.objects.filter(method='Transfer').order_by('-date')[start:end]
                for item in transfer:
                    diff_activity.append(item)
            
            if 'like' in query:
                print('like!')
                if address:
                    print(1)
                    like = UserAction.objects.filter(
                        Q(user__username=address) | Q(whom_follow__username=address),
                        method='like', 
                    ).order_by('-date')[start:end]
                    print(like.all())
                else:
                    print(2)
                    like = UserAction.objects.filter(method='like').order_by('-date')[start:end]
                    print(like.all())
                for item in like:
                    diff_activity.append(item)
            
            if 'follow' in query:
                print('follow!')
                if address:
                    follow = UserAction.objects.filter(
                        Q(user__username=address) | Q(whom_follow__username=address),
                        method='follow', 
                    ).order_by('-date')[start:end]
                else:
                    follow = UserAction.objects.filter(method='follow').order_by('-date')[start:end]
                for item in follow:
                    diff_activity.append(item)
            if 'mint' in query:
                print('mint!')
                if address:
                    mint = TokenHistory.objects.filter(
                        Q(new_owner__username=address),
                        method='Mint', 
                    ).order_by('-date')[start:end]
                else:
                    mint = TokenHistory.objects.filter(method='Mint').order_by('-date')[start:end]
                for item in mint:
                    diff_activity.append(item)
            if 'burn' in query:
                print('burn!')
                if address:
                    burn = TokenHistory.objects.filter(
                        Q(new_owner__username=address),
                        method='Burn', 
                    ).order_by('-date')[start:end]
                else:
                    burn = TokenHistory.objects.filter(method='Burn').order_by('-date')[start:end]
                for item in burn:
                    diff_activity.append(item)
            if 'bids' in query:
                print('Bid!')
                if address:
                    bid = BidsHistory.objects.filter(
                        user__username=address,
                        method='Bet'
                    ).order_by('-date')[start:end]
                else:
                    bid = BidsHistory.objects.filter(
                        method='Bet'
                    ).order_by('-date')[start:end]
                for item in bid:
                    diff_activity.append(item)
            if 'list' in query:
                print('Listing!')
                if address:
                    listing = ListingHistory.objects.filter(
                        user__username=address,
                    ).order_by('-date')[start:end]
                else:
                    listing = ListingHistory.objects.all() \
                        .order_by('-date')[start:end]
                for item in listing:
                    diff_activity.append(item)
        else:
            print('query:', query)
            if address:
                actions = UserAction.objects.filter(
                        Q(user__username=address) | Q(whom_follow__username=address)
                    )[start:end]
                diff_activity.extend(actions)
                history = TokenHistory.objects.filter(
                        Q(new_owner__username=address) | Q(old_owner__username=address)
                    ).exclude(Q(method='Burn') | Q(method='Transfer'))[start:end]
                diff_activity.extend(history)
                listing = ListingHistory.objects.filter(user__username=address)[start:end]
                diff_activity.extend(listing)
            else:
                actions = UserAction.objects.all().order_by('-date')[start:end]
                diff_activity.extend(actions)
                history = TokenHistory.objects.exclude(Q(method='Burn') | Q(method='Transfer')).order_by('-date')[start:end]
                diff_activity.extend(history)
                bit = BidsHistory.objects.all().order_by('-date')[start:end]
                diff_activity.extend(bit)
                listing = ListingHistory.objects.all().order_by('-date')[start:end]
                diff_activity.extend(listing)
        print(len(diff_activity))
        quick_sort(diff_activity)
        print(len(diff_activity))
        
        sorted_activity = []

        for activ in diff_activity:
            try:
                user_from = getattr(activ, 'user')
            except AttributeError:
                user_from = getattr(activ, 'old_owner')
            
            try:
                user_to = getattr(activ, 'whom_follow')
            except AttributeError:
                try:
                    user_to = getattr(activ, 'new_owner')
                except AttributeError:
                    user_to = None
            try:
                price = getattr(activ, 'price')
            except AttributeError:
                price = ''
            
            if price:
                price = price / DECIMALS[activ.token.currency]
            
            try:
                quantity = getattr(activ, 'quantity')
            except AttributeError:
                quantity = None

            item = {
                'token_id': activ.token.id if activ.token else None,
                'token_image': activ.token.media,
                'token_name': activ.token.name if activ.token else None,
                'method': activ.method,
                'from_id': user_from.id if user_from else None,
                'from_image': get_media_if_exists(user_from, 'avatar') if user_from else None,
                'from_address': user_from.username if user_from else None,
                'from_name': user_from.display_name if user_from else None,
                'to_id': user_to.id if user_to else None,
                'to_image': get_media_if_exists(user_to, 'avatar') if user_to else None,
                'to_address': user_to.username if user_to else None,
                'to_name': user_to.display_name if user_to else None,
                'date': activ.date,
                'price': price,
                'quantity': quantity
            }
            if item not in sorted_activity:
                sorted_activity.append(item)
        print(len(sorted_activity))
        return Response(sorted_activity, status=status.HTTP_200_OK)


class GetBestDealView(APIView):

    def get(self, request, days):

        end_date = datetime.datetime.today()
        start_date = start_date - datetime.timedelta(days=days)

        tokens = TokenHistory.objects.filter(method='Buy').filter(date__range=[start_date, end_date])
     
        buyers = {}
        sellers = {}
        for token in tokens:
            buyer = token.new_owner.username
            seller = token.old_owner.username
            cost = token.price
            if len(buyers) < 15:
                if buyers.get(buyer):
                    buyers[buyer] += cost
                else:
                    buyers[buyer] = cost
            if len(sellers) < 15:
                if sellers.get(seller):
                    sellers[seller] += cost
                else:
                    sellers[seller] = cost

        buyers_list = []
        sellers_list = []
        buyers_list.append(buyers)
        sellers_list.append(sellers)

        return Response({'buyers': buyers_list, 'sellers': sellers_list}, status=status.HTTP_200_OK)


class GetLikedView(APIView):

    def get(self, request, address):
        pass
