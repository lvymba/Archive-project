#Algorithm of python with MS SQL Server v.1.4

import pyodbc

#Тестовые данные, используемые на моём пк
#server = 'LAPTOP-DCD8MES6\SQLEXPRESS'
#database = 'Emulation'
#Позже будет переопределено, чтобы алгоритм получал не только название сервера, но также логин и пароль.


user_defined_types = {}

#Подключение к серверу и определённой базе данных
def connect_db(server, database):
	cnxn = pyodbc.connect('Driver={ODBC Driver 17 for SQL Server};'
						  'Server='+server+';'
						  'Database='+database+';'
						  'Trusted_Connection=yes;'
						  'autocommit=True')
	return cnxn

#Получение списка хранимых процедур
def get_procedure_list(cursor, database):
    #Создаём новый запрос, позволяющий получить список кортежей, содержащих схему и название ХП, и вызываем его
	query = f"""
		SELECT SPECIFIC_SCHEMA, SPECIFIC_NAME
		FROM {database}.INFORMATION_SCHEMA.ROUTINES
		WHERE ROUTINE_TYPE = 'PROCEDURE' 
		AND LEFT(ROUTINE_NAME, 3) NOT IN ('sp_', 'xp_', 'ms_')"""
	cursor.execute(query)

	#Преобразуем список кортежей в список строк в формате [schema].[name]
	rows = cursor.fetchall()
	rows = [f"{row[0]}.{row[1]}" for row in rows]
	rows.sort()

	return rows

#получение словаря, где ключ - название ХП, значения - её параметры
def get_procedure_params(cursor, sp_list):
	result = {}
	#Для каждой процедуры в списке sp_list получаем данные о её параметрах
	#Записываем как кортежи из трёх элементов, где первый элемент - название, 
	#второй - тип данных, третий - является ли он OUT
	for procedure in sp_list:
		cursor.execute(f"""
			SELECT 
				\'Parameter_name\' = name,
				\'Type\' = type_name(user_type_id),
				\'is_output\' = is_output
			FROM sys.parameters WHERE object_id = object_id(\'{procedure}\')""")
		rows = cursor.fetchall()
		result[procedure] = rows

	return result

#cursor - курсор, sp_dict - словарь {процедура : параметры}, name - название, args - аргументы
def exec_procedure(cursor, sp_dict, name, args = []):
	params = sp_dict[name]

	cursor.execute(f"""
		SET NOCOUNT ON
		DECLARE @RC int
		{' '.join([f'DECLARE {param[0]} ' +	
			(param[1] if param[1] not in user_defined_types else  f'dbo.{param[1]}') 
			for param in params ])}

		{set_values(params, args)}

		EXEC @RC = {name}
		{set_SP_params(params)}

		SELECT {', '.join([param[0] for param in params if param[2]])}""")

	result = cursor.fetchall()
	return result


def set_SP_params(params):
	result = []

	for i, param in enumerate(params):
		if param[2]:
			result.append(f'{param[0]} = {param[0]} OUTPUT')
		else:
			result.append(f'{param[0]} = {param[0]}')
	return ', '.join(result)

#Получаем словарь, где ключ - пользовательский табличный тип, значение - список имён столбцов этого типа
def get_user_types_data(cursor):
	cursor.execute(f"""
		SELECT
			TYPE.name,
			COL.name
		FROM sys.table_types TYPE
		JOIN sys.columns COL ON COL.object_id = TYPE.type_table_object_id
		ORDER BY TYPE.name""")
	rows = cursor.fetchall()
	for row in rows:
		if row[0] in user_defined_types:
			user_defined_types[row[0]].append(row[1])
		else:
			user_defined_types[row[0]] = [row[1]]

#Установказначений для всех параметров ХП
def set_values(params, args):
	result = []

	for i, param in enumerate(params):
		if param[1] in user_defined_types:
			result.append(set_user_type_values(param, args[i]))
			continue
		if not param[2]:
			result.append(f'SET {param[0]} = {args[i]}')

	return ' '.join(result)

#Установка значений для параметров, принадлежащих к пользовательским табличным типам
def set_user_type_values(param, value_list):
	result = []

	for value in value_list:
		result.append(f'INSERT INTO {param[0]}({", ".join([col for col in user_defined_types[param[1]]])}) ' 
			+ f'VALUES {value}')
	return ' '.join(result)

#Получение столбцов columns из таблицы table
def get_table_data(cursor, table, columns='*'):
	cursor.execute(f'SELECT {columns} FROM {table}')
	result = cursor.fetchall()
	return list(map(list, result))

#Запись данных values в таблицу table
def set_table_data(cursor, table, values):
	cursor.execute(' '.join([f'INSERT INTO {table} VALUES {value}' for value in values]))


#=========================================================================================================================#
#Пример выполнения функций	
server = input("Имя сервера: ")
database = input("Имя БД: ")
cnxn = connect_db(server, database)
cursor = cnxn.cursor()

print(f'\nВсе пользовательские типы\n')
get_user_types_data(cursor)
print(user_defined_types)

print('\nСписок всех ХП на сервере {server} в БД {database}\n')
sp_test_list = get_procedure_list(cursor, database)
for obj in sp_test_list:
	print(obj)

print('\nСловарь, содержащий процедуры и их парметры\n')
sp_dict = get_procedure_params(cursor, sp_test_list)
for key in sp_dict.keys():
	print(f'{key} : {sp_dict[key]}')


print('\nGример вызова хранимой процедуры:')
print('Установка значений параметров для emu.RndGenType2Obj3:\n')
arguments1 = [[(1,4.5), (2,4.2), (3,3.6), (4,7.1), (5,2.4), (6,5.0), (7,6.3), (8,3.8), (9,7.5), (10,3.5)], 10, 10, 0.25]
print(set_values(sp_dict['emu.RndGenType2Obj3'], arguments1))

print('\nСписок выходных параметров для emu.RndGenType2Obj3:\n')
print(exec_procedure(cursor, sp_dict, 'emu.RndGenType2Obj3', arguments1))



print('\nУстановка значений параметров для emu.OptType2Alg1:\n')
arguments2 = [50, 70, 1000, 4.7, 1.9]
print(set_values(sp_dict['emu.OptType2Alg1'], arguments2))

print('\nСписок выходных параметров для emu.OptType2Alg1:\n')
print(exec_procedure(cursor, sp_dict, 'emu.OptType2Alg1', arguments2))


cursor.close()
cnxn.close()
#=========================================================================================================================#