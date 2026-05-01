SpaceShooter:
	python Main.py Examples/SpaceShooter.blend -minify -no_mangle=[close_shop,buy_item,add_cash,open_shop]
BlackCat:
	python Main.py Examples/BlackCat.blend -minify -no_mangle=[reset,close_shop,buy_item,open_shop]
GBTest:
	QT_QPA_PLATFORM=xcb GDK_BACKEND=x11 SDL_VIDEODRIVER=x11 python Main.py Examples/GBTest.blend
RemoveSubmodules:
	git rm --cached -f Py2Gb Py2Js PyRapier2d Third\ Party/ZGB Third\ Party/ngdevkit-examples Third\ Party/ngdevkit blender-curve-to-svg tinifyjs