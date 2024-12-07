# importing package 
import matplotlib.pyplot as plt 
import pandas as pd 
import matplotlib.pyplot as plt

# create data 
df = pd.DataFrame([[60, 30, 2000], [70, 20, 2001], [60, 30, 2002]], 
				columns=['Max_temp', 'Min_temp', 'Year']) 
# view data 
print(df) 

df.plot(x=df.columns[2], 
        kind='bar', 
        stacked=False, 
        title='Grouped Bar Graph with dataframe') 
plt.xticks(rotation=0, ha='right')
plt.xlabel("temp")
plt.ylabel("Temp")
plt.show()