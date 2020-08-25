from flask import Flask, request, abort, redirect

from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.models import *

from urllib.parse import parse_qsl
import uuid

from config import Config
from database import db_session, init_db
from models.user import Users
from models.product import Products
from models.cart import Cart
from models.order import Orders
from models.item import Items
from models.linepay import LinePay


app = Flask(__name__)

line_bot_api = LineBotApi(Config.CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(Config.CHANNEL_SECRET)


@app.teardown_appcontext
def shutdown_session(exception=None):
    db_session.remove()


@app.route("/liff", methods=['GET'])
def liff():
    redirect_url = request.args.get('redirect_url')

    return redirect(redirect_url)


@app.route("/confirm")
def confirm():
    transaction_id = request.args.get('transactionId')
    order = db_session.query(Orders).filter(Orders.transaction_id == transaction_id).first()

    if order:
        line_pay = LinePay()
        line_pay.confirm(transaction_id=transaction_id, amount=order.amount)

        order.is_pay = True
        db_session.commit()

        message = order.display_receipt()
        line_bot_api.push_message(to=order.user_id, messages=message)

        return '<h1>Your payment is successful. thanks for your purchase.</h1>'


@app.route("/callback", methods=['POST'])
def callback():
    # get X-Line-Signature header value
    signature = request.headers['X-Line-Signature']

    # get request body as text
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    # handle webhook body
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print("Invalid signature. Please check your channel access token/channel secret.")
        abort(400)

    return 'OK'


@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):

    get_or_create_user(event.source.user_id)

    message_text = str(event.message.text).lower()

    cart = Cart(user_id=event.source.user_id)

    message = None

    if message_text in ["what is your story?", "story"]:
        message = [
            ImageSendMessage(
                original_content_url='https://i.imgur.com/DKzbk3l.jpg',
                preview_image_url='https://i.imgur.com/DKzbk3l.jpg'
            ), StickerSendMessage(
                package_id='11537',
                sticker_id='52002734'
            )
        ]

    elif message_text in ['i am ready to order.', 'add']:
        message = Products.list_all()

    elif "i'd like to have" in message_text:

        product_name = message_text.split(',')[0]
        num_item = message_text.rsplit(':')[1]

        product = db_session.query(Products).filter(Products.name.ilike(product_name)).first()

        if product:

            cart.add(product=product_name, num=num_item)

            confirm_template = ConfirmTemplate(
                text='Sure, {} {}, anything else?'.format(num_item, product_name),
                actions=[
                    MessageAction(label='Add', text='add'),
                    MessageAction(label="That's it", text="That's it")
                ])

            message = TemplateSendMessage(alt_text='anything else?', template=confirm_template)

        else:
            message = TextSendMessage(text="Sorry, We don't have {}.".format(product_name))

        print(cart.bucket())

    elif message_text in ['my cart', 'cart', "that's it"]:

        if cart.bucket():
            message = cart.display()
        else:
            message = TextSendMessage(text='Your cart is empty now.')

    elif message_text == 'empty cart':

        cart.reset()

        message = TextSendMessage(text='Your cart is empty now.')

    if message:
        line_bot_api.reply_message(
            event.reply_token,
            message)


@handler.add(PostbackEvent)
def handle_postback(event):
    data = dict(parse_qsl(event.postback.data))

    action = data.get('action')

    if action == 'checkout':

        user_id = event.source.user_id

        cart = Cart(user_id=user_id)

        if not cart.bucket():
            message = TextSendMessage(text='Your cart is empty now.')

            line_bot_api.reply_message(event.reply_token, [message])

            return 'OK'

        order_id = uuid.uuid4().hex

        total = 0
        items = []

        for product_name, num in cart.bucket().items():
            product = db_session.query(Products).filter(Products.name.ilike(product_name)).first()

            item = Items(product_id=product.id,
                         product_name=product.name,
                         product_price=product.price,
                         order_id=order_id,
                         quantity=num)

            items.append(item)

            total += product.price * int(num)

        cart.reset()

        line_pay = LinePay()
        info = line_pay.pay(product_name='LSTORE',
                            amount=total,
                            order_id=order_id,
                            product_image_url=Config.STORE_IMAGE_URL)

        pay_web_url = info['paymentUrl']['web']
        transaction_id = info['transactionId']

        order = Orders(id=order_id,
                       transaction_id=transaction_id,
                       is_pay=False,
                       amount=total,
                       user_id=user_id)

        db_session.add(order)

        for item in items:
            db_session.add(item)

        db_session.commit()

        message = TemplateSendMessage(
            alt_text='Thank you, please go ahead to the payment.',
            template=ButtonsTemplate(
                text='Thank you, please go ahead to the payment.',
                actions=[
                    URIAction(label='Pay NT${}'.format(order.amount),
                              uri='{liff_url}?redirect_url={url}'.format(
                                  liff_url=Config.LIFF_URL,
                                  url=pay_web_url))
                ]))

        line_bot_api.reply_message(event.reply_token, [message])

    return 'OK'


@handler.add(FollowEvent)
def handle_follow(event):

    get_or_create_user(event.source.user_id)

    line_bot_api.reply_message(
        event.reply_token, TextSendMessage(text='Hi! Welcome to LSTORE.'))


@handler.add(UnfollowEvent)
def handle_unfollow():
    print("Got Unfollow event")


def get_or_create_user(user_id):
    user = db_session.query(Users).filter_by(id=user_id).first()

    if not user:
        profile = line_bot_api.get_profile(user_id)
        user = Users(id=user_id, nick_name=profile.display_name, image_url=profile.picture_url)
        db_session.add(user)
        db_session.commit()

    return user


@app.before_first_request
def init_products():
    # init db
    result = init_db()
    if result:
        init_data = [Products(name='Coffee',
                              product_image_url='https://i.imgur.com/DKzbk3l.jpg',
                              price=150,
                              description='nascetur ridiculus mus. Donec quam felis, ultricies'),
                     Products(name='Tea',
                              product_image_url='https://i.imgur.com/PRTxyhq.jpg',
                              price=120,
                              description='adipiscing elit. Aenean commodo ligula eget dolor'),
                     Products(name='Cake',
                              price=180,
                              product_image_url='https://i.imgur.com/PRm22i8.jpg',
                              description='Aenean massa. Cum sociis natoque penatibus')]
        db_session.bulk_save_objects(init_data)
        db_session.commit()


if __name__ == "__main__":
    init_products()
    app.run()