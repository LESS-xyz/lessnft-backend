from datetime import datetime, timedelta

from celery import shared_task
from src.store.models import Bid, Status, Token
from src.store.services.auction import end_auction


@shared_task(name="remove_pending_tokens")
def remove_pending_tokens():
    expiration_date = datetime.today() - timedelta(days=1)
    tokens = Token.objects.filter(
        status__in=(Status.PENDING, Status.FAILED),
        updated_at__lte=expiration_date,
    )
    print(f"Pending {len(tokens)} tokens")
    tokens.delete()


@shared_task(name="end_auction_checker")
def end_auction_checker():
    tokens = Token.objects.committed().filter(
        end_auction__lte=datetime.today(),
    )
    for token in tokens:
        end_auction(token)

@shared_task(name="incorrect_bid_checker")
def incorrect_bid_checker():
    bids = Bid.objects.committed()
    for bid in bids:
        user_balance = bid.token.currency.network.contract_call(
                method_type='read',
                contract_type='token',
                address=bid.token.currency.address,
                function_name='balanceOf',
                input_params=(bid.user.username,),
                input_type=('address',),
                output_types=('uint256',),
            )

        allowance = bid.token.currency.network.contract_call(
                method_type='read',
                contract_type='token',
                address=bid.token.currency.address,
                function_name='allowance',
                input_params=(
                    bid.user.username,
                    bid.token.currency.network.exchange_address
                ),
                input_type=('address', 'address'),
                output_types=('uint256',),
            )

        if user_balance < bid.amount * bid.quantity or allowance < bid.amount * bid.quantity:
            bid.state = Status.EXPIRED
            bid.save()
