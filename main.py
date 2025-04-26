import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ConversationHandler,
    CallbackQueryHandler,
    ContextTypes
)
from sqlalchemy.orm import joinedload
from datetime import datetime
from database import Session, User, Playlist, Track
from config import Config

# Состояния для ConversationHandler
GET_NAME, GET_DESC = range(2)

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


async def format_duration(seconds: int) -> str:
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    return f"{hours:02d}ч {minutes:02d}мин"

# ========== ОБНОВЛЕННОЕ ПРИВЕТСТВИЕ ========== #
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "\U0001F3B5 *Добро пожаловать в Лаврушку!*\n\n"
        "_Здесь вы можете:_\n"
        "• Создавать персональные плейлисты\n"
        "• Сохранять любимые треки\n"
        "• Управлять своей коллекцией музыки\n\n"
        "✨ _Используйте кнопки ниже для навигации_"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

# ========== СОЗДАНИЕ ПЛЕЙЛИСТА ========== #
async def new_playlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
        await query.message.reply_text("\U0001F3B6 Введите название плейлиста:")
    else:
        await update.message.reply_text("\U0001F3B6 Введите название плейлиста:")
    return GET_NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['name'] = update.message.text.strip()
    await update.message.reply_text("\U0001F4DD Введите описание (или /skip):")
    return GET_DESC

async def get_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    desc = update.message.text.strip()
    name = context.user_data.get('name')
    user_data = update.effective_user
    
    with Session() as session:
        user = session.query(User).filter_by(tg_id=user_data.id).first()
        if not user:
            user = User(
                tg_id=user_data.id,
                first_name=user_data.first_name or "Пользователь",
                username=user_data.username
            )
            session.add(user)
            session.commit()
        
        playlist = Playlist(
            name=name,
            description=desc,
            user_id=user.id
        )
        session.add(playlist)
        session.commit()

    await update.message.reply_text(f"✅ *Плейлист «{name}» создан!*", parse_mode="Markdown")
    return ConversationHandler.END

async def skip_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = context.user_data.get('name')
    user_data = update.effective_user
    
    with Session() as session:
        user = session.query(User).filter_by(tg_id=user_data.id).first()
        if not user:
            user = User(
                tg_id=user_data.id,
                first_name=user_data.first_name or "Пользователь",
                username=user_data.username
            )
            session.add(user)
            session.commit()
        
        playlist = Playlist(
            name=name,
            user_id=user.id
        )
        session.add(playlist)
        session.commit()

    await update.message.reply_text(f"✅ *Плейлист «{name}» создан!*", parse_mode="Markdown")
    return ConversationHandler.END

# ========== МОИ ПЛЕЙЛИСТЫ -> ВСЕ ПЛЕЙЛИСТЫ ========== #
async def show_all_playlists(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
        send = query.message.edit_text
    else:
        send = update.message.reply_text
        
    with Session() as session:
        playlists = session.query(Playlist).all()
        
        if not playlists:
            return await send("📭 Пока нет ни одного плейлиста.")
            
        total_duration = sum(pl.duration for pl in playlists)
        text = (
            f"📂 *Все плейлисты*\n"
            f"└ Всего: {len(playlists)}\n"
            f"└ Общая длительность: {await format_duration(total_duration)}"
        )
        
        keyboard = [
            [InlineKeyboardButton(
                f"📀 {pl.name} [@{pl.user.username}]", 
                callback_data=f"plinfo_{pl.id}"
            )] 
            for pl in playlists
        ]
        keyboard.append([InlineKeyboardButton("➕ Создать свой", callback_data="new_playlist")])
        
        await send(
            text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

# ========== ИНФОРМАЦИЯ О ПЛЕЙЛИСТЕ (ОБЩЕДОСТУПНАЯ) ========== #
async def show_playlist_info(update: Update, context: ContextTypes.DEFAULT_TYPE, playlist_id: int = None):
    query = update.callback_query
    await query.answer()
    
    playlist_id = int(query.data.split("_")[1])
    with Session() as session:
        playlist = session.get(Playlist, playlist_id)
        if not playlist:
            return await query.message.reply_text("❌ Плейлист не найден!")
        
        is_owner = (playlist.user.tg_id == update.effective_user.id)
        
        duration = await format_duration(playlist.duration)
        created_at = playlist.created_at.strftime("%d.%m.%Y")
        tracks_count = len(playlist.tracks)
        owner_name = playlist.user.first_name or "Аноним"
        
        text = (
            f"🎧 *{playlist.name}*\n"
            f"_{playlist.description or 'Нет описания'}_\n\n"
            f"📅 Создан: `{created_at}`\n"
            f"🎶 Треков: `{tracks_count}`\n"
            f"👤 Владелец: {owner_name}\n\n"
            f"⚙️ *Действия:*"
        )
        
        # Создаем клавиатуру
        keyboard = []
        
        # Основная кнопка воспроизведения
        keyboard.append([InlineKeyboardButton("▶️ Воспроизвести", callback_data=f"play_{playlist.id}")])
        
        # Кнопки для владельца
        if is_owner:
            keyboard.append([
                InlineKeyboardButton("✏️ Редактировать", callback_data=f"edit_{playlist.id}"),
                InlineKeyboardButton("🗑️ Удалить", callback_data=f"del_{playlist.id}")
            ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if playlist.cover_url:
            await query.message.reply_photo(
                photo=playlist.cover_url,
                caption=text,
                parse_mode="Markdown",
                reply_markup=reply_markup
            )
        else:
            await query.message.reply_text(
                text,
                parse_mode="Markdown",
                reply_markup=reply_markup
            )

# ========== ЗАЩИЩЕННОЕ УДАЛЕНИЕ ========== #
async def confirm_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    playlist_id = int(query.data.split("_")[1])
    
    with Session() as session:
        playlist = session.get(Playlist, playlist_id)
        # Проверка владельца
        if playlist.user.tg_id != update.effective_user.id:
            return await query.message.reply_text("❌ Вы не можете удалить чужой плейлист!")
        
        name = playlist.name
        session.delete(playlist)
        session.commit()
    
    await query.message.reply_text(f"🗑 *Плейлист «{name}» удален!*", parse_mode="Markdown")

# ========== ПРОСЛУШИВАНИЕ ========== #
async def play_music(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    playlist_id = int(query.data.split("_")[1])
    with Session() as session:
        playlist = session.get(Playlist, playlist_id)
        if not playlist.tracks:
            return await query.message.reply_text("😞 В плейлисте нет треков.")
        for track in playlist.tracks:
            await context.bot.send_audio(
                chat_id=update.effective_chat.id,
                audio=track.file_id,
                title=track.title
            )

# ========== ДОБАВЛЕНИЕ ТРЕКА ========== #
async def add_track(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.audio:
        return await update.message.reply_text("❌ Отправьте аудиофайл!")

    with Session() as session:
        user = session.query(User).filter_by(tg_id=update.effective_user.id).first()
        if not user or not user.playlists:
            return await update.message.reply_text("❌ Сначала создайте плейлист!")

        # Явно перезагружаем плейлист с треками
        playlist = session.query(Playlist).options(
            joinedload(Playlist.tracks)
        ).filter_by(id=user.playlists[0].id).first()

        track_title = update.message.audio.title or "Без названия"
        track_duration = update.message.audio.duration or 0

        track = Track(
            title=track_title,
            file_id=update.message.audio.file_id,
            duration=track_duration,
            playlist_id=playlist.id
        )

        playlist.duration += track_duration
        session.add(track)
        session.commit()

        # Сохраняем данные для сообщения до закрытия сессии
        playlist_name = playlist.name
        total_duration = playlist.duration

    # Отправляем сообщение вне сессии
    await update.message.reply_text(
        f"🎵 *Трек успешно добавлен!*\n\n"
        f"▫️ Название: {track_title}\n"
        f"▫️ Плейлист: {playlist_name}\n"
        f"▫️ Общая длительность: {await format_duration(total_duration)}",
        parse_mode="Markdown"
    )

# ========== РЕДАКТИРОВАНИЕ ПЛЕЙЛИСТА (УДАЛЕНИЕ ТРЕКОВ) ========== #
async def edit_playlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    playlist_id = int(query.data.split("_")[1])
    with Session() as session:
        playlist = session.get(Playlist, playlist_id)
            
        if not playlist.tracks:
            return await query.message.reply_text("🎵 В плейлисте нет треков для удаления")
            
        keyboard = [
            [InlineKeyboardButton(
                f"❌ {track.title} ({await format_duration(track.duration)})", 
                callback_data=f"deltrack_{track.id}"
            )] 
            for track in playlist.tracks
        ]
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data=f"plinfo_{playlist.id}")])
        
        await query.message.edit_text(
            f"🎧 Выберите треки для удаления из плейлиста *{playlist.name}*:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def confirm_track_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    track_id = int(query.data.split("_")[1])
    
    with Session() as session:
        try:
            # Получаем трек и связанный плейлист
            track = session.get(Track, track_id)
            if not track:
                await query.message.reply_text("❌ Трек не найден!")
                return

            playlist = track.playlist
            track_title = track.title
            
            # Обновляем длительность плейлиста
            playlist.duration -= track.duration
            
            # Удаляем трек и сохраняем изменения
            session.delete(track)
            session.commit()
            
            # Сохраняем ID плейлиста для дальнейшего использования
            playlist_id = playlist.id
            
        except Exception as e:
            session.rollback()
            logger.error(f"Ошибка при удалении трека: {e}")
            await query.message.reply_text("❌ Произошла ошибка!")
            return

    # Уведомляем об успешном удалении
    await query.message.reply_text(f"🗑 Трек *{track_title}* удален!", parse_mode="Markdown")
    
    # Вызываем обновленную информацию о плейлисте
    await show_playlist_info(update, context, playlist_id=playlist_id)

# ========== ЗАПУСК БОТА ========== #
def main():
    app = ApplicationBuilder().token(Config.TG_TOKEN).build()

    # Командные обработчики
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("all", show_all_playlists))
    app.add_handler(CommandHandler("add_track", lambda u, c: u.message.reply_text(
        "🎵 Пришлите аудиофайл — и я добавлю его в плейлист!")))
    app.add_handler(CommandHandler("edit_playlist", edit_playlist))

    # Обработчики создания плейлиста
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("new_playlist", new_playlist),
                      CallbackQueryHandler(new_playlist, pattern="^new_playlist$")],
        states={
            GET_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            GET_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_desc),
                       CommandHandler("skip", skip_desc)]
        },
        fallbacks=[],
        per_user=True
    )
    app.add_handler(conv_handler)

    # CallbackQueryHandler для навигации
    app.add_handler(CommandHandler("all", show_all_playlists))
    app.add_handler(CallbackQueryHandler(confirm_delete, pattern="^del_"))
    app.add_handler(CallbackQueryHandler(show_playlist_info, pattern="^plinfo_"))
    app.add_handler(CallbackQueryHandler(edit_playlist, pattern="^edit_"))
    app.add_handler(CallbackQueryHandler(confirm_track_delete, pattern="^deltrack_"))
    app.add_handler(CallbackQueryHandler(play_music, pattern="^play_"))

    # Приём аудио
    app.add_handler(MessageHandler(filters.AUDIO, add_track))

    app.run_polling()

if __name__ == "__main__":
    main()
